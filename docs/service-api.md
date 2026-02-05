# Service API

## Log Streaming (SSE)

Clients MAY reconnect using `Last-Event-ID`.
The server guarantees:
- monotonic event ids starting at 1
- resume from id + 1
- final `event: end`
- Last-Event-ID header overrides last_id query param.

### Edge Cases
- **Garbage Last-Event-ID**: If the `Last-Event-ID` header contains non-numeric values, the server responds with **HTTP 400**.
- **Negative Last-Event-ID**: Negative values are clamped to 0 defensively.
- **Future ID**: If `Last-Event-ID` > `len(logs)`, the stream returns only `event: end`.
- **Reconnect after completion**: If the job is already finished and `Last-Event-ID` matches the total log count, the stream returns only `event: end`.

## File System

### `/api/fs/roots`
Returns a list of allowed root entry points.

**Contract:**
Each entry in the `roots` list guarantees the following fields:
- `id`: The logical identifier (e.g., `hub`, `system`).
- `path`: The absolute path on the server.
- `token`: An opaque navigation token required for subsequent `/api/fs/list` calls.

Example:
```json
{
  "roots": [
    { "id": "hub", "path": "/home/user/repos", "token": "..." },
    { "id": "system", "path": "/home/user", "token": "..." }
  ]
}
```

## Job Submission & Dispatch

### `include_paths_by_repo` Semantics
When submitting a job with `include_paths_by_repo`, the keys in the dictionary MUST exactly match the repository folder name as it exists on the Hub disk.
- The backend performs **no automatic normalization** (no lowercasing, no path stripping).
- **Strict Mode**: If `strict_include_paths_by_repo: true` is sent, missing keys trigger a `400 Bad Request` (Job Failed) instead of a fallback. This is the default for WebUI "Combined" jobs.
- **Soft Mode (Default)**: If strict mode is false, a missing key logs a warning and falls back to the global `include_paths` (or full scan if none).
- This ensures predictability and prevents ambiguous matches in complex directory structures.
