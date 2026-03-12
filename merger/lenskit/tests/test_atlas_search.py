import pytest
from pathlib import Path
import json

from merger.lenskit.atlas.search import AtlasSearch
from merger.lenskit.atlas.registry import AtlasRegistry

def test_atlas_search(tmp_path):
    registry_path = tmp_path / "registry.sqlite"
    registry = AtlasRegistry(registry_path)

    registry.register_machine("m1", "host1")
    registry.register_root("r1", "m1", "abs_path", "/tmp/r1")

    # Create dummy inventory
    inv_path = tmp_path / "inv1.jsonl"
    with open(inv_path, "w") as f:
        f.write(json.dumps({"rel_path": "a/b/c.txt", "name": "c.txt", "ext": ".txt", "size_bytes": 100, "mtime": "2023-01-01T00:00:00Z"}) + "\n")
        f.write(json.dumps({"rel_path": "a/d.md", "name": "d.md", "ext": ".md", "size_bytes": 200, "mtime": "2023-01-02T00:00:00Z"}) + "\n")

    registry.create_snapshot("s1", "m1", "r1", "hash1", "complete")
    registry.update_snapshot_artifacts("s1", {"inventory": str(inv_path)})

    registry.close()

    searcher = AtlasSearch(registry_path)

    # Test basic search
    res = searcher.search()
    assert len(res) == 2

    # Test query
    res = searcher.search(query="c.txt")
    assert len(res) == 1
    assert res[0]["name"] == "c.txt"

    # Test ext
    res = searcher.search(ext=".md")
    assert len(res) == 1
    assert res[0]["name"] == "d.md"

    # Test ext without dot
    res = searcher.search(ext="md")
    assert len(res) == 1
    assert res[0]["name"] == "d.md"

    # Test size
    res = searcher.search(min_size=150)
    assert len(res) == 1
    assert res[0]["name"] == "d.md"
