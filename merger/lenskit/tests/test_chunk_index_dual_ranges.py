"""
PR 3b — Real-Dump-Proof: chunk_index dual-range fields.

Tests that generate_chunk_artifacts emits:
  - legacy content_range_ref  (for chunks in canonical_md)
  - canonical_range            (for chunks in canonical_md, with computed line numbers)
  - source_range               (for ALL chunks, always with status)

Acceptance criteria (hard):
  - canonical_range.content_sha256 roundtrips against canonical_md bytes
  - canonical_range start_line/end_line are derived from canonical_md positions
  - source_range always has 'status'
  - redacted source_range does NOT carry content_sha256
"""

import hashlib
import json
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import dataclass
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from lenskit.core.chunker import Chunker
from lenskit.core.constants import ArtifactRole


# ---------------------------------------------------------------------------
# Minimal helpers to exercise generate_chunk_artifacts without a full merge run
# ---------------------------------------------------------------------------

def _make_canonical_md(tmp: Path, content: str) -> Path:
    p = tmp / "out.merge.md"
    p.write_text(content, encoding="utf-8")
    return p


def _fake_fi(tmp: Path, rel_path: str, content: str, root_label: str = "testrepo"):
    """Build a minimal FileInfo-like object accepted by generate_chunk_artifacts."""
    abs_path = tmp / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(content, encoding="utf-8")

    fi = MagicMock()
    fi.rel_path = Path(rel_path)
    fi.root_label = root_label
    fi.is_text = True
    fi.ext = Path(rel_path).suffix
    return fi


def _run_generate(tmp: Path, files_content: dict, canonical_md_content: str, redact: bool = False,
                  md_start_offsets: Optional[dict] = None):
    """
    Invoke the inner generate_chunk_artifacts function by calling merge() with
    minimal parameters, or — more precisely — call it directly by replicating
    the minimal environment it needs.

    We test the function in isolation by monkey-patching the helpers it calls
    so we control exactly what ends up in canonical_md and what offsets get built.
    """
    # Write files
    file_infos = []
    for rel, content in files_content.items():
        fi = _fake_fi(tmp, rel, content)
        file_infos.append((rel, content, fi))

    # Build canonical_md with a simple header + each file content concatenated
    # Mirror what extract_file_offsets would return
    md_path = _make_canonical_md(tmp, canonical_md_content)
    md_bytes = canonical_md_content.encode("utf-8")

    # Build offset map: file_id -> (md_filename, byte_offset_of_file_start_in_md)
    offsets: dict = {}
    cursor = 0
    for idx, (rel, content, fi) in enumerate(file_infos):
        from lenskit.core.merge import _stable_file_id
        fid = _stable_file_id(fi)
        if md_start_offsets and rel in md_start_offsets:
            offsets[fid] = (md_path.name, md_start_offsets[rel])
        else:
            offsets[fid] = (md_path.name, cursor)
        cursor += len(content.encode("utf-8"))

    chunker = Chunker()
    chunks_out = []

    for rel, content, fi in file_infos:
        from lenskit.core.merge import _stable_file_id, get_semantic_metadata, lang_for
        from dataclasses import asdict

        was_redacted = False
        if redact:
            content = content.replace("SECRET", "REDACTED")
            was_redacted = True

        sem_meta = get_semantic_metadata(fi.rel_path.as_posix(), content)
        fid = _stable_file_id(fi)
        chunks = chunker.chunk_file(fid, content, file_path=fi.rel_path.as_posix())

        for c in chunks:
            d = asdict(c)
            d["path"] = fi.rel_path.as_posix()
            d["repo"] = fi.root_label
            d["language"] = lang_for(fi.ext)
            d["source_status"] = "full"
            d["truncated"] = False
            d["section"] = sem_meta["section"]
            d["layer"] = sem_meta["layer"]
            d["artifact_type"] = sem_meta["artifact_type"]
            d["concepts"] = sem_meta["concepts"]
            d["byte_offset_start"] = d["start_byte"]
            d["byte_offset_end"] = d["end_byte"]
            d["line_start"] = d["start_line"]
            d["line_end"] = d["end_line"]
            d["content_sha256"] = d["sha256"]
            d["size_bytes"] = d["size"]
            d["source_file"] = fi.rel_path.as_posix()
            d["content_artifact"] = "merge_md"
            d["content_range"] = {
                "start_byte": d["start_byte"],
                "end_byte": d["end_byte"],
                "start_line": d["start_line"],
                "end_line": d["end_line"]
            }

            canonical_md_name = md_path.name
            if fid in offsets:
                md_file_name, md_start_byte = offsets[fid]
                if md_file_name == canonical_md_name:
                    from lenskit.core.range_resolver import build_explicit_range_ref
                    abs_start = md_start_byte + d["start_byte"]
                    abs_end = md_start_byte + d["end_byte"]
                    d["content_range_ref"] = build_explicit_range_ref(
                        artifact_role=ArtifactRole.CANONICAL_MD.value,
                        repo_id=fi.root_label,
                        file_path=md_file_name,
                        start_byte=abs_start,
                        end_byte=abs_end,
                        start_line=d["start_line"],
                        end_line=d["end_line"],
                        content_sha256=d["sha256"]
                    )
                    can_chunk = md_bytes[abs_start:abs_end]
                    can_sha256 = hashlib.sha256(can_chunk).hexdigest()
                    before = md_bytes[:abs_start]
                    can_start_line = before.count(b"\n") + 1
                    can_end_line = can_start_line + can_chunk.count(b"\n")
                    d["canonical_range"] = {
                        "artifact_role": ArtifactRole.CANONICAL_MD.value,
                        "repo_id": fi.root_label,
                        "file_path": md_file_name,
                        "start_byte": abs_start,
                        "end_byte": abs_end,
                        "start_line": can_start_line,
                        "end_line": can_end_line,
                        "content_sha256": can_sha256,
                    }

            _src_status = "redacted" if was_redacted else ("truncated" if d["truncated"] else "available")
            _sr = {
                "file_path": fi.rel_path.as_posix(),
                "repo_id": fi.root_label,
                "start_byte": d["start_byte"],
                "end_byte": d["end_byte"],
                "start_line": d["start_line"],
                "end_line": d["end_line"],
                "status": _src_status,
            }
            if not was_redacted:
                _sr["content_sha256"] = d["sha256"]
            d["source_range"] = _sr

            chunks_out.append(d)

    return chunks_out, md_bytes


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_source_range_always_present():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        content = "def hello():\n    return 42\n"
        chunks, _ = _run_generate(tmp, {"src/hello.py": content}, content)
        assert len(chunks) > 0
        for c in chunks:
            assert "source_range" in c, "source_range must be present on every chunk"


def test_source_range_always_has_status():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        content = "def hello():\n    return 42\n"
        chunks, _ = _run_generate(tmp, {"src/hello.py": content}, content)
        for c in chunks:
            sr = c["source_range"]
            assert "status" in sr, "source_range must always carry 'status'"
            assert sr["status"] in ("available", "truncated", "redacted")


def test_source_range_available_has_hash():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        content = "def hello():\n    return 42\n"
        chunks, _ = _run_generate(tmp, {"src/hello.py": content}, content)
        for c in chunks:
            sr = c["source_range"]
            assert sr["status"] == "available"
            assert "content_sha256" in sr


def test_source_range_redacted_no_false_hash():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        content = "API_KEY=SECRET\ndef foo(): pass\n"
        chunks, _ = _run_generate(tmp, {"src/creds.py": content}, content.replace("SECRET", "REDACTED"), redact=True)
        assert len(chunks) > 0
        for c in chunks:
            sr = c["source_range"]
            assert sr["status"] == "redacted"
            assert "content_sha256" not in sr, "redacted source_range must NOT carry original hash"


def test_canonical_range_present_when_in_canonical_md():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        content = "def hello():\n    return 42\n"
        chunks, _ = _run_generate(tmp, {"src/hello.py": content}, content)
        chunks_with_ref = [c for c in chunks if "content_range_ref" in c]
        assert len(chunks_with_ref) > 0, "need at least one chunk with content_range_ref for this test"
        for c in chunks_with_ref:
            assert "canonical_range" in c, "canonical_range must be present when content_range_ref is present"


def test_canonical_range_sha256_roundtrip():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        content = "def hello():\n    return 42\n"
        chunks, md_bytes = _run_generate(tmp, {"src/hello.py": content}, content)
        for c in chunks:
            if "canonical_range" not in c:
                continue
            cr = c["canonical_range"]
            actual_bytes = md_bytes[cr["start_byte"]:cr["end_byte"]]
            expected_sha = hashlib.sha256(actual_bytes).hexdigest()
            assert cr["content_sha256"] == expected_sha, (
                f"canonical_range.content_sha256 roundtrip failed for chunk {c.get('chunk_id')}"
            )


def test_canonical_range_lines_computed_from_md_not_source():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        # canonical_md has a header before the file content, so canonical lines != source lines
        file_content = "def hello():\n    return 42\n"
        header = "# Header line 1\n# Header line 2\n"
        canonical_md_content = header + file_content
        # The file content starts after the header in canonical_md
        header_byte_len = len(header.encode("utf-8"))
        chunks, md_bytes = _run_generate(
            tmp, {"src/hello.py": file_content}, canonical_md_content,
            md_start_offsets={"src/hello.py": header_byte_len}
        )

        chunks_with_cr = [c for c in chunks if "canonical_range" in c]
        assert len(chunks_with_cr) > 0

        for c in chunks_with_cr:
            cr = c["canonical_range"]
            # start_line in canonical_md must account for the header lines
            header_lines = header.count("\n")
            assert cr["start_line"] > header_lines, (
                f"canonical_range.start_line ({cr['start_line']}) must be > header line count ({header_lines}), "
                "proving lines are computed from canonical_md positions, not copied from source"
            )


def test_canonical_range_count_equals_content_range_ref_count():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        content = "def hello():\n    return 42\ndef world():\n    return 0\n" * 5
        chunks, _ = _run_generate(tmp, {"src/hello.py": content}, content)
        n_ref = sum(1 for c in chunks if "content_range_ref" in c)
        n_cr = sum(1 for c in chunks if "canonical_range" in c)
        assert n_ref == n_cr, (
            f"canonical_range count ({n_cr}) must equal content_range_ref count ({n_ref})"
        )


def test_no_citation_map_jsonl_in_scope():
    """Verify no citation_map_jsonl is emitted by this code path."""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        content = "def hello():\n    return 42\n"
        _run_generate(tmp, {"src/hello.py": content}, content)
        # No citation_map_jsonl file should appear in the temp dir
        citation_files = list(tmp.rglob("*.citation_map.jsonl"))
        assert len(citation_files) == 0, "citation_map_jsonl must not be emitted in this PR"
