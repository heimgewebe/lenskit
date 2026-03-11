# ADR 006: Content enrichment is optional and mode-dependent

## Status
Accepted

## Context
Scanning entire disks and computing content hashes or text stats is computationally expensive. Running it by default leads to performance degradation and unmanageable output artifacts.

## Decision
Content enrichment is explicitly optional and must be requested via a specific execution mode. Basic filesystem metadata (size, time, owner) is always captured. Content inspection (e.g., MIME typing, text verification, full-text parsing) is decoupled and gated by the `content` mode.

## Consequences
- Requires explicit CLI flags or mode definitions to trigger deep file analysis.
- Performance remains acceptable for base inventory scans.
- Ensures the `inventory.jsonl` contract handles conditional fields (like `is_text` or `line_count`) gracefully.