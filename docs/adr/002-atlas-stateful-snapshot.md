# ADR 002: Atlas is stateful and snapshot-driven

## Status
Accepted

## Context
A simple filesystem scanner provides a current view of reality but has no memory of the past. To enable comparison, history tracking, and an evolving understanding of the system, we need to track not just what is there now, but how it changes over time.

## Decision
Atlas is a stateful system. Every meaningful scan execution produces a persistent "Snapshot" artifact. This artifact explicitly records the state of a root on a machine at a specific point in time, and serves as the baseline for delta calculations and history tracking.

## Consequences
- Requires persistent storage for snapshot metadata.
- Enables time-based diffs and delta mechanics.
- Precludes ephemeral scans from being the primary mode of operation if history is to be maintained.