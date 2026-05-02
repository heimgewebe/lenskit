"""
Core implementation of SQLite schema and index builder.
"""

import sqlite3
import json
import hashlib
import datetime
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from ..core.range_resolver import resolve_range_ref

logger = logging.getLogger(__name__)

INDEX_SCHEMA_VERSION = "v1"

def _compute_file_sha256(path: Path) -> str:
    """Compute SHA256 of a file."""
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return "ERROR"

def create_schema(conn: sqlite3.Connection) -> None:
    """Create the SQLite schema for retrieval."""
    c = conn.cursor()

    # 1. Meta Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS index_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # 2. Chunks Table (Structured Data)
    c.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            repo_id TEXT,
            path TEXT,
            path_norm TEXT,
            layer TEXT,
            artifact_type TEXT,
            start_byte INTEGER,
            end_byte INTEGER,
            start_line INTEGER,
            end_line INTEGER,
            content_sha256 TEXT,
            size_bytes INTEGER,
            language TEXT,
            content_range_ref TEXT,
            source_file TEXT
        )
    """)

    # 3. FTS Table (Full Text Search)
    # Using separate content table pattern (manual sync)
    c.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            chunk_id UNINDEXED,
            content,
            path_tokens
        )
    """)

    # Indices
    c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_repo ON chunks(repo_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path_norm)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_layer ON chunks(layer)")

    conn.commit()

def build_index(dump_path: Path, chunk_path: Path, db_path: Path, config_payload: Optional[Dict[str, Any]] = None) -> None:
    """
    Builds the SQLite index from artifacts.
    """
    if db_path.exists():
        try:
            db_path.unlink()
        except OSError as e:
            raise RuntimeError(f"Could not remove existing DB {db_path}: {e}")

    conn = sqlite3.connect(str(db_path))
    try:
        create_schema(conn)
        c = conn.cursor()

        # Diagnostics counters
        stats = {
            "total_lines": 0,
            "empty_lines": 0,
            "invalid_json_lines": 0,
            "missing_chunk_id_lines": 0,
            "ingested_chunks_count": 0,
            "fts_hydrated_from_range_ref": 0,
        }

        # 2. Ingest Chunks
        batch_size = 500
        batch_chunks = []
        batch_fts = []

        with chunk_path.open("r", encoding="utf-8") as f:
            for line in f:
                stats["total_lines"] += 1
                if not line.strip():
                    stats["empty_lines"] += 1
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    stats["invalid_json_lines"] += 1
                    continue

                cid = chunk.get("chunk_id")
                if not cid:
                    stats["missing_chunk_id_lines"] += 1
                    continue

                repo = chunk.get("repo") or chunk.get("repo_id") or "unknown"
                path = chunk.get("path", "")
                path_norm = path.lower().replace("\\", "/")

                layer = chunk.get("layer", "unknown")
                atype = chunk.get("artifact_type", "unknown")

                sb = chunk.get("start_byte", 0)
                eb = chunk.get("end_byte", 0)
                sl = chunk.get("start_line", 0)
                el = chunk.get("end_line", 0)

                sha = chunk.get("sha256") or chunk.get("content_sha256") or ""
                size = chunk.get("size") or chunk.get("size_bytes") or 0
                lang = chunk.get("language", "")

                # FTS Content: prefer inline content, fall back to content_range_ref
                content_text = chunk.get("content") or ""
                if not content_text:
                    raw_ref = chunk.get("content_range_ref")
                    if raw_ref is not None:
                        # raw_ref may already be a dict or a JSON string (stored either way)
                        if isinstance(raw_ref, str):
                            try:
                                raw_ref = json.loads(raw_ref)
                            except json.JSONDecodeError:
                                raw_ref = None
                        if isinstance(raw_ref, dict):
                            try:
                                resolved = resolve_range_ref(dump_path, raw_ref)
                                content_text = resolved["text"]
                                stats["fts_hydrated_from_range_ref"] += 1
                            except ValueError as e:
                                # Hash mismatch or schema violation — controlled fail, no unverified text in FTS
                                raise RuntimeError(
                                    f"FTS hydration failed for chunk '{cid}': {e}"
                                ) from e
                            except FileNotFoundError as e:
                                logger.warning(
                                    "FTS hydration skipped for chunk '%s': %s",
                                    cid, e,
                                )
                            except Exception as e:
                                logger.warning(
                                    "FTS hydration skipped for chunk '%s' (unexpected error): %s",
                                    cid, e,
                                )
                    else:
                        logger.debug(
                            "Chunk '%s' has no inline content and no content_range_ref; FTS content will be empty.",
                            cid,
                        )

                # Path tokens: split by common delimiters
                path_tokens = path_norm.replace("/", " ").replace(".", " ").replace("_", " ").replace("-", " ")

                batch_chunks.append((
                    cid, repo, path, path_norm, layer, atype,
                    sb, eb, sl, el, sha, size, lang,
                    json.dumps(chunk.get("content_range_ref")) if chunk.get("content_range_ref") else None,
                    chunk.get("source_file", path)
                ))

                batch_fts.append((
                    cid, content_text, path_tokens
                ))

                stats["ingested_chunks_count"] += 1

                if len(batch_chunks) >= batch_size:
                    c.executemany("""
                        INSERT INTO chunks (chunk_id, repo_id, path, path_norm, layer, artifact_type,
                                          start_byte, end_byte, start_line, end_line, content_sha256, size_bytes, language, content_range_ref, source_file)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, batch_chunks)

                    c.executemany("""
                        INSERT INTO chunks_fts (chunk_id, content, path_tokens)
                        VALUES (?, ?, ?)
                    """, batch_fts)

                    batch_chunks = []
                    batch_fts = []

        # Final batch
        if batch_chunks:
            c.executemany("""
                INSERT INTO chunks (chunk_id, repo_id, path, path_norm, layer, artifact_type,
                                  start_byte, end_byte, start_line, end_line, content_sha256, size_bytes, language, content_range_ref, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch_chunks)

            c.executemany("""
                INSERT INTO chunks_fts (chunk_id, content, path_tokens)
                VALUES (?, ?, ?)
            """, batch_fts)

        # 1. Metadata (written last to include stats)
        dump_sha = _compute_file_sha256(dump_path)
        chunk_sha = _compute_file_sha256(chunk_path)

        # Try to extract config_sha256 and version from config_payload if passed,
        # or leave empty. Often config_payload is just {"cli_args": ...} right now,
        # but we can try to find config_sha256. If not available in payload, we
        # might default to empty string, but the caller should supply it.
        config_sha256 = (config_payload or {}).get("config_sha256", "")
        lenskit_version = (config_payload or {}).get("lenskit_version", "unknown")

        # Use real UTC timestamp
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        meta_items = [
            ("schema_version", INDEX_SCHEMA_VERSION),
            ("canonical_dump_index_sha256", dump_sha),
            ("chunk_index_sha256", chunk_sha),
            ("created_at", now_utc),
            ("config_json", json.dumps(config_payload or {})),
            ("config_sha256", config_sha256),
            ("lenskit_version", lenskit_version)
        ]

        # Add stats to meta
        for k, v in stats.items():
            meta_items.append((f"ingest.{k}", str(v)))

        c.executemany("INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)", meta_items)

        conn.commit()
    finally:
        conn.close()

    # Emit warning if issues found
    if stats["invalid_json_lines"] > 0 or stats["missing_chunk_id_lines"] > 0:
        logger.warning(
            "Index ingest had issues (invalid_json=%d, missing_id=%d). Total lines: %d",
            stats["invalid_json_lines"],
            stats["missing_chunk_id_lines"],
            stats["total_lines"],
        )

def verify_index(db_path: Path, dump_path: Path, chunk_path: Path) -> bool:
    """
    Verifies if the index is fresh and matches the artifacts.
    Returns True if valid, False if stale/invalid.
    """
    if not db_path.exists():
        return False

    try:
        conn = sqlite3.connect(str(db_path))
        try:
            c = conn.cursor()

            row_dump = c.execute("SELECT value FROM index_meta WHERE key='canonical_dump_index_sha256'").fetchone()
            if not row_dump: # fallback for older schemas if any
                row_dump = c.execute("SELECT value FROM index_meta WHERE key='dump_sha256'").fetchone()

            row_chunk = c.execute("SELECT value FROM index_meta WHERE key='chunk_index_sha256'").fetchone()
        finally:
            conn.close()

        if not row_dump or not row_chunk:
            return False

        stored_dump = row_dump[0]
        stored_chunk = row_chunk[0]

        current_dump = _compute_file_sha256(dump_path)
        if current_dump != stored_dump:
            return False

        current_chunk = _compute_file_sha256(chunk_path)
        if current_chunk != stored_chunk:
            return False

        return True

    except Exception:
        return False
