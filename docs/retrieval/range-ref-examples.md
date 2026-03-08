## Example 1: Explicit Bundle-Backed `range_ref` (Before & After - No change)

When the chunk index contains an explicit `content_range_ref` pointing to the bundle (e.g. `canonical_md`), the output strictly retains this explicit provenance. The new fallback logic is ignored.

```json
{
  "chunk_id": "c1",
  "repo_id": "r1",
  "path": "src/main.py",
  "range": "1-1",
  "score": 0.8,
  "layer": "core",
  "type": "code",
  "sha256": "h1",
  "range_ref": {
    "artifact_role": "canonical_md",
    "repo_id": "r1",
    "file_path": "lenskit_merge.md",
    "start_byte": 1024,
    "end_byte": 1048,
    "start_line": 1,
    "end_line": 1,
    "content_sha256": "h1"
  },
  "why": { ... }
}
```

---

## Example 2: Dynamically Derived Source-Backed Fallback (New Behavior)

When the index was built with the generator injecting `source_file`, `start_byte`, and `end_byte` into the SQLite schema, but *no* explicit `content_range_ref` exists, the system safely falls back to a `derived_range_ref` pointing directly to the original file in the hub. The main `range_ref` property strictly remains absent.

```json
{
  "chunk_id": "c2",
  "repo_id": "r1",
  "path": "src/main.py",
  "range": "1-1",
  "score": 0.8,
  "layer": "core",
  "type": "code",
  "sha256": "h1",
  "derived_range_ref": {
    "artifact_role": "source_file",
    "repo_id": "r1",
    "file_path": "src/main.py",
    "start_byte": 0,
    "end_byte": 24,
    "start_line": 1,
    "end_line": 1,
    "content_sha256": "h1"
  },
  "why": { ... }
}
```
