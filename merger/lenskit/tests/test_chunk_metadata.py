import sys
from pathlib import Path
import pytest
import dataclasses

# Add repo root to path
sys.path.append(str(Path(__file__).parents[3]))

from merger.lenskit.core.chunker import Chunker
from merger.lenskit.core.merge import get_semantic_metadata, generate_architecture_summary, scan_repo

def test_chunk_id_determinism():
    chunker = Chunker()
    file_id = "FILE:f_12345"
    content = "line 1\nline 2\nline 3"
    file_path = "src/main.py"

    chunks1 = chunker.chunk_file(file_id, content, file_path=file_path)
    chunks2 = chunker.chunk_file(file_id, content, file_path=file_path)

    assert len(chunks1) == 1
    assert chunks1[0].chunk_id == chunks2[0].chunk_id

    # Check that ID changes if path changes (even if content is same)
    chunks3 = chunker.chunk_file(file_id, content, file_path="src/other.py")
    assert chunks1[0].chunk_id != chunks3[0].chunk_id

    # Check that ID changes if content changes
    chunks4 = chunker.chunk_file(file_id, "line 1\nline 2\nline 3 changed", file_path=file_path)
    assert chunks1[0].chunk_id != chunks4[0].chunk_id

    # Check ID length (truncated to 20)
    assert len(chunks1[0].chunk_id) == 20

def test_semantic_metadata_extraction():
    # Test core/merge.py
    path = "merger/lenskit/core/merge.py"
    content = "def merge_logic(): pass # bundle logic"
    meta = get_semantic_metadata(path, content)

    assert meta["section"] == "merge"
    assert meta["layer"] == "core"
    assert meta["artifact_type"] == "code"
    assert "merge_logic" in meta["concepts"]
    # "bundling" is mapped from keyword "bundle"
    assert "bundling" in meta["concepts"]

    # Test tests/test_math.py
    path = "merger/lenskit/tests/test_math.py"
    content = "import pytest"
    meta = get_semantic_metadata(path, content)

    assert meta["section"] == "test_math"
    assert meta["layer"] == "test"
    assert meta["artifact_type"] == "code"

    # Test docs/README.md
    path = "docs/README.md"
    content = "# Introduction"
    meta = get_semantic_metadata(path, content)

    assert meta["section"] == "README"
    assert meta["layer"] == "docs"
    assert meta["artifact_type"] == "documentation"

    # Test unknown layer
    path = "other/foo.bar"
    content = ""
    meta = get_semantic_metadata(path, content)
    assert meta["layer"] == "unknown"
    assert meta["concepts"] == []

def test_architecture_summary_generation(tmp_path):
    # Setup robust FileInfo objects via scan_repo
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Create file structure
    (repo_root / "merger/lenskit/core").mkdir(parents=True)
    (repo_root / "merger/lenskit/core/merge.py").touch()
    (repo_root / "merger/lenskit/core/chunker.py").touch()

    (repo_root / "merger/lenskit/tests").mkdir(parents=True)
    (repo_root / "merger/lenskit/tests/test_merge.py").touch()

    (repo_root / "docs").mkdir(parents=True)
    (repo_root / "docs/intro.md").touch()

    # Use scan_repo to get real FileInfo objects
    summary = scan_repo(repo_root, calculate_md5=False)
    files = summary["files"]

    arch_summary = generate_architecture_summary(files)

    assert "# Lenskit Architecture Snapshot" in arch_summary
    assert "## Layer Distribution" in arch_summary
    # Note: Depending on scan_repo ordering and path handling, counts should match
    assert "- core: 2 files" in arch_summary
    assert "- test: 1 files" in arch_summary
    assert "- docs: 1 files" in arch_summary

    assert "## Core Modules" in arch_summary
    assert "- merge" in arch_summary
    assert "- chunker" in arch_summary

    assert "## Test Coverage Map" in arch_summary
    assert "- `merger/lenskit/tests/`: 1 tests" in arch_summary

def test_chunk_jsonl_fields():
    # Ensure new fields are present in chunk representation
    chunker = Chunker()
    file_id = "FILE:f_test"
    content = "test content # bundle"
    file_path = "merger/lenskit/core/test.py"

    chunks = chunker.chunk_file(file_id, content, file_path=file_path)
    sem_meta = get_semantic_metadata(file_path, content)

    # Simulate what write_reports_v2 does
    if dataclasses.is_dataclass(chunks[0]):
        d = dataclasses.asdict(chunks[0])
    else:
        d = chunks[0].__dict__.copy()

    d["section"] = sem_meta["section"]
    d["layer"] = sem_meta["layer"]
    d["artifact_type"] = sem_meta["artifact_type"]
    d["concepts"] = sem_meta["concepts"]

    assert "section" in d
    assert "layer" in d
    assert "artifact_type" in d
    assert "concepts" in d
    assert d["section"] == "test"
    assert d["layer"] == "core"
    assert d["artifact_type"] == "code"
    assert "bundling" in d["concepts"]

if __name__ == "__main__":
    pytest.main([__file__])
