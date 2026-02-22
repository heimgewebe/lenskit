# ADR 001: Secure Filesystem Navigation (Token-Based & Opt-In)

## Status
Accepted

## Context
The `rLens` service requires a mechanism to browse the filesystem (via Folder Picker) and scan directory structures (via Atlas).
Users expressed a need for **maximal functional comfort**, specifically the ability to browse the entire system starting from the root (`/`), rather than being restricted to the Hub directory.

However, standard implementation of absolute path browsing poses significant security risks and triggers static analysis warnings (e.g., CodeQL `py/path-injection`) because user-supplied strings are used to construct filesystem paths.

## Decision
We implement a "Secure Capability" architecture that balances functionality with strict governance and scanner compliance.

### 1. Restricted Root Access
Browsing the system root (`/`) via API is prohibited. The service is restricted to navigation within allowlisted directories (Hub, Merges directory, and User Home).

Future system-wide scans, if ever introduced, must be implemented as a separate, local-only capability with explicit governance (e.g. job-based inventory with redaction), rather than widening the filesystem allowlist for general browsing.

### 2. Token-Based Navigation (The "Hard Cut")
To satisfy security scanners and prevent path traversal, the API no longer accepts raw path strings for navigation.
*   **Protocol**: The server issues opaque, HMAC-signed tokens representing paths.
*   **Client**: The client sends these tokens back to list directories or select targets.
*   **Verification**: The server verifies the signature and expiration (TTL) of the token, then re-validates the encoded path against the current security allowlist.

Legacy parameters (e.g., `?path=/abs/path`) have been removed.

### 3. TrustedPath Type Boundary
We introduced a `TrustedPath` dataclass in the backend.
*   `resolve_fs_path` returns a `TrustedPath` instance after validation.
*   Filesystem operations (`_list_dir`) expect a `TrustedPath`.
This creates a visible type boundary between "untrusted user input" and "safe filesystem operations", aiding both code review and static analysis.

## Consequences
*   **Positive**: CodeQL "path injection" warnings are resolved by design. Filesystem access is strictly limited to authorized roots.
*   **Negative**: "Quick and dirty" API calls using manual path strings are no longer possible; clients must obtain a valid token first (e.g., via `/api/fs/roots`).
*   **Maintenance**: Requires `RLENS_FS_TOKEN_SECRET` (or `RLENS_TOKEN` fallback) to be managed securely.

## References
*   `merger/repoLens/service/fs_resolver.py`
*   `merger/repoLens/service/security.py`
