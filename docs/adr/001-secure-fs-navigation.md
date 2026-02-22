# ADR 001: Secure Filesystem Navigation (Token-Based & Opt-In)

## Status
Accepted

## Context
The `rLens` service requires a mechanism to browse the filesystem (via Folder Picker) and scan directory structures (via Atlas).
Users expressed a need for **maximal functional comfort**, specifically the ability to browse the entire system starting from the root (`/`), rather than being restricted to the Hub directory.

However, standard implementation of absolute path browsing poses significant security risks and triggers static analysis warnings (e.g., CodeQL `py/path-injection`) because user-supplied strings are used to construct filesystem paths.

## Decision
We implement a "Secure Capability" architecture that balances functionality with strict governance and scanner compliance.

### 1. Gated Root Access (Operator Mode)
Browsing the system root (`/`) via API is disabled by default. The service is normally restricted to navigation within allowlisted directories (Hub, Merges directory, and User Home).

Root access can be explicitly enabled for administrative tasks ("Operator Mode") only under strict security constraints:
1.  **Environment Flag**: `RLENS_ALLOW_FS_ROOT=1` must be set.
2.  **Operator Flag**: `RLENS_OPERATOR_MODE=1` must be set.
3.  **Local Only**: The service must be bound to a loopback interface (`localhost`/`127.0.0.1`).
4.  **Auth Required**: A security token or secret must be configured.

This ensures that root access is auditible, intentional, and not exposed to the network by accident.

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
