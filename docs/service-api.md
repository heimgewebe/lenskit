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

## Context Lookup

### `POST /api/context_lookup`

Typed read-only facade over stored `context_bundle` artifacts. Returns the context bundle payload for a given artifact ID without re-executing any query.

**Auth:** Provide a token using either `Authorization: Bearer <token>` (preferred) or the `token` query parameter.

**Request:**
```json
{ "id": "qart-<hex>" }
```

**Response (ok):**
```json
{
  "status": "ok",
  "id": "qart-abc123",
  "context_bundle": { "query": "main", "hits": [...] },
  "provenance": { "source_query": "main", "timestamp": "2024-01-01T00:00:00+00:00", "index_id": "test-art", "run_id": null },
  "created_at": "2024-01-01T00:00:00+00:00",
  "warnings": []
}
```

**Response (not found / wrong type):**
```json
{
  "status": "not_found",
  "id": "qart-abc123",
  "context_bundle": null,
  "provenance": null,
  "created_at": null,
  "warnings": ["Artifact 'qart-abc123' has type 'query_trace', not 'context_bundle'"]
}
```

**Notes:**
- Read-only. Never recomputes, reconstructs, or re-executes a query.
- Only returns artifacts of type `context_bundle`. If the ID exists but refers to a different artifact type, `status: "not_found"` is returned with a warning naming the actual type — no foreign artifact data is leaked.
- Context bundle artifacts are stored automatically when `/api/query` produces a `context_bundle`, for example via `build_context_bundle=true` or an output profile / context mode that includes a context bundle. In those cases, the ID is returned in `artifact_ids.context_bundle` of the query response.
- `trace=true` alone stores a `query_trace`; it does not by itself guarantee `artifact_ids.context_bundle`.
- Extra request fields are rejected with HTTP 422 (`additionalProperties: false` per contract).
- Contract: `merger/lenskit/contracts/context-lookup.v1.schema.json`

## Diagnostics

### `GET /api/diagnostics`

Read-only lookup facade over the persisted diagnostics snapshot.

**Auth:** Standard service auth via `verify_token` (for example `Authorization: Bearer <token>`).

**Behavior:**
- Reads `.gewebe/cache/diagnostics.snapshot.json`.
- Does **not** trigger `POST /api/diagnostics/rebuild`.
- Does **not** modify, rewrite, or mutate the snapshot file.
- Returns a lookup envelope (`status`, `snapshot`, `freshness`, `warnings`) instead of projecting snapshot fields to top-level.

**Response shape:**
```json
{
  "status": "ok",
  "snapshot": { "schema_version": "diagnostics.snapshot.v1", "...": "..." },
  "freshness": {
    "generated_at": "2026-01-01T00:00:00Z",
    "ttl_hours": 24,
    "is_stale": false,
    "age_seconds": 120
  },
  "warnings": []
}
```

**Status semantics:**
- `status` is the **lookup status** (`ok`, `not_found`, `error`).
- Staleness is represented by `freshness.is_stale` (TTL exceeded).
- The endpoint does not remap lookup status to `warn` for stale snapshots.

**Notes:**
- `not_found`: snapshot file does not exist.
- `error`: snapshot file exists but cannot be parsed as JSON.
- `freshness` is `null` if `generated_at` is absent/invalid or if lookup fails.
- Contract: `merger/lenskit/contracts/diagnostics-lookup.v1.schema.json`.

## Trace Lookup

### `POST /api/trace_lookup`

Typed read-only facade over stored `query_trace` artifacts. Returns the trace payload for a given artifact ID without re-executing any query.

**Auth:** `Authorization: Bearer <token>` required.

**Request:**
```json
{ "id": "qart-<hex>" }
```

**Response (ok):**
```json
{
  "status": "ok",
  "id": "qart-abc123",
  "trace": { "query_input": "...", "timings": {}, "..." : "..." },
  "provenance": { "source_query": "main", "timestamp": "2024-01-01T00:00:00+00:00", "index_id": "test-art", "run_id": null },
  "created_at": "2024-01-01T00:00:00+00:00",
  "warnings": []
}
```

**Response (not found / wrong type):**
```json
{
  "status": "not_found",
  "id": "qart-abc123",
  "trace": null,
  "provenance": null,
  "created_at": null,
  "warnings": ["Artifact 'qart-abc123' has type 'context_bundle', not 'query_trace'"]
}
```

**Notes:**
- Read-only. Never recomputes or re-executes a query.
- Only returns artifacts of type `query_trace`. If the ID exists but refers to a different artifact type, `status: "not_found"` is returned with a warning naming the actual type — no foreign artifact data is leaked.
- Artifacts are stored automatically when `/api/query` is called with `trace=true`. The ID is returned in `artifact_ids.query_trace` of the query response.
- Extra request fields are rejected with HTTP 422 (`additionalProperties: false` per contract).
- Contract: `merger/lenskit/contracts/trace-lookup.v1.schema.json`

## Job Submission & Dispatch

### `include_paths_by_repo` Semantics
When submitting a job with `include_paths_by_repo`, the keys in the dictionary MUST exactly match the repository folder name as it exists on the Hub disk.
- The backend performs **no automatic normalization** (no lowercasing, no path stripping).
- **Strict Mode**: If `strict_include_paths_by_repo: true` is sent, missing keys trigger a `400 Bad Request` (Job Failed) instead of a fallback. This is the default for WebUI "Combined" jobs.
- **Soft Mode (Default)**: If strict mode is false, a missing key logs a warning and falls back to the global `include_paths` (or full scan if none).
- This ensures predictability and prevents ambiguous matches in complex directory structures.
