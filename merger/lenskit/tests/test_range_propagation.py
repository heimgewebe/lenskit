import pytest
from pathlib import Path
from merger.lenskit.core.merge import write_reports_v2, FileInfo

def test_range_propagation_to_canonical_md(tmp_path):
    hub_path = tmp_path / "hub"
    hub_path.mkdir()
    merges_dir = tmp_path / "merges"
    merges_dir.mkdir()

    repo_dir = hub_path / "r1"
    repo_dir.mkdir()
    f1 = repo_dir / "test.py"
    f1.write_text("def hello():\n    pass\n", encoding="utf-8")

    fi = FileInfo(
        root_label="r1",
        abs_path=f1,
        rel_path=Path("test.py"),
        size=f1.stat().st_size,
        is_text=True,
        md5="dummy",
        category="source",
        tags=[],
        ext=".py"
    )

    repo_summaries = [{"name": "r1", "root": repo_dir, "files": [fi]}]

    res = write_reports_v2(
        merges_dir=merges_dir,
        hub=hub_path,
        repo_summaries=repo_summaries,
        detail="dev",
        mode="single",
        max_bytes=10000,
        plan_only=False,
        output_mode="dual"
    )

    import json
    chunks = []
    with res.chunk_index.open() as f:
        for line in f:
            chunks.append(json.loads(line))

    assert len(chunks) == 1
    chunk = chunks[0]

    assert "content_range_ref" in chunk
    ref = chunk["content_range_ref"]
    assert ref["artifact_role"] == "canonical_md"
    assert ref["file_path"] == res.canonical_md.name

    # Let's actually verify the byte offsets in the canonical_md!
    with res.canonical_md.open("rb") as f:
        md_bytes = f.read()

    start_byte = ref["start_byte"]
    end_byte = ref["end_byte"]

    extracted = md_bytes[start_byte:end_byte]
    assert extracted.decode("utf-8") == "def hello():\n    pass\n"
