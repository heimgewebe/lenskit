# Atlas sparse-file accounting v1 — proof

Date: 2026-07-10

## Problem

The historical home snapshot represented file length only. A live read-only census on `heim-pc` found 3,842 readable `core`, `core.<pid>` or `*.core` files with approximately 33.6 TB apparent length but only approximately 15.3 GB allocated blocks. The filesystem itself used about 426 GB. Treating apparent length as disk consumption therefore produced a materially misleading result.

## Contract

Atlas keeps existing fields for compatibility:

- `size_bytes` and `stats.total_bytes` are apparent/logical lengths from `stat.st_size`;
- `bytes` in `top_dirs` remains apparent/logical size.

Atlas adds:

- per-file `allocated_size_bytes` and `is_sparse`;
- `stats.total_allocated_bytes`;
- sparse file count plus apparent and allocated sparse totals;
- directory `subtree_allocated_bytes`;
- `allocated_bytes` beside apparent `bytes` in top-directory rows.

On POSIX, allocated size uses `st_blocks * 512`. On platforms without `st_blocks`, Atlas falls back to apparent size and records the basis as `st_blocks_512_or_apparent_fallback`.

## Core-dump boundary

Default Atlas scans exclude only conventional dump names:

- `core`;
- `core.<digit...>`;
- `*.core`.

This deliberately does not exclude legitimate source files such as `core.py`. Callers may still opt out of all default excludes with the existing `no_default_excludes` boundary. System-preset requests show the same core patterns in their effective hard-exclude list.

## Presentation

The generated Markdown and Web UI display allocated and logical sizes separately. Historical artifacts without the new field remain readable by falling back to `total_bytes`.

## Operational decision

No core file is deleted by this change. Atlas is an observer and map, not a cleanup engine or backup. File deletion requires separate ownership, retention and recovery decisions.

## Non-claims

Allocated blocks do not equal backup size, compressed transfer size, deduplicated storage, quota billing or recoverability. A terminal Atlas snapshot does not prove that the filesystem is healthy, complete, backed up or free of sensitive data.
