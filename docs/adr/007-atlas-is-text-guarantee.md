# ADR 007: `is_text` Guarantee is Mode-Dependent

## Status
Accepted

## Context
Determining if a file is text or binary can be expensive. In a massive filesystem, reading file headers just to determine `is_text` for the base inventory slows down discovery scans significantly.

## Decision
The `is_text` field in the `atlas-inventory.v1.schema.json` is strictly optional. It is *only* guaranteed to be present and accurate when the `content` enrichment mode is active for the scan. Base `inventory` scans must not be expected to provide this field.

## Consequences
- Systems parsing the inventory JSONL must gracefully handle the absence of `is_text`.
- If `is_text` is required by downstream consumers, they must trigger a scan with the `content` mode enabled.