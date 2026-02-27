"""
Core implementation of SQLite schema and index builder.
"""

import sqlite3
import json
import hashlib
import datetime
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

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

def create_schema(conn: sqlite3.Connection):
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
            language TEXT
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

    # 4. Files Table (File Metadata)
    c.execute("""
        CREATE TABLE IF NOT EXISTS files (
            file_id TEXT PRIMARY KEY,
            repo_id TEXT,
            path TEXT,
            file_sha256 TEXT,
            size_bytes INTEGER,
            language TEXT
        )
    """)

    # Indices
    c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_repo ON chunks(repo_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path_norm)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_layer ON chunks(layer)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_files_repo ON files(repo_id)")

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
    create_schema(conn)
    c = conn.cursor()

    # Diagnostics counters
    stats = {
        "total_lines": 0,
        "empty_lines": 0,
        "invalid_json_lines": 0,
        "missing_chunk_id_lines": 0,
        "ingested_chunks_count": 0,
        "ingested_files_count": 0
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

            # FTS Content
            content_text = chunk.get("content", "")

            # Path tokens: split by common delimiters
            path_tokens = path_norm.replace("/", " ").replace(".", " ").replace("_", " ").replace("-", " ")

            batch_chunks.append((
                cid, repo, path, path_norm, layer, atype,
                sb, eb, sl, el, sha, size, lang
            ))

            batch_fts.append((
                cid, content_text, path_tokens
            ))

            stats["ingested_chunks_count"] += 1

            if len(batch_chunks) >= batch_size:
                c.executemany("""
                    INSERT INTO chunks (chunk_id, repo_id, path, path_norm, layer, artifact_type,
                                      start_byte, end_byte, start_line, end_line, content_sha256, size_bytes, language)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                              start_byte, end_byte, start_line, end_line, content_sha256, size_bytes, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch_chunks)

        c.executemany("""
            INSERT INTO chunks_fts (chunk_id, content, path_tokens)
            VALUES (?, ?, ?)
        """, batch_fts)

    # 3. Ingest Files (from sidecar via dump_index)
    # Load dump_index.json to find sidecar
    sidecar_path = None
    run_id = "unknown"
    try:
        dump_data = json.loads(dump_path.read_text(encoding="utf-8"))
        run_id = dump_data.get("run_id", "unknown")
        sidecar_entry = dump_data.get("artifacts", {}).get("sidecar_json")
        if sidecar_entry and sidecar_entry.get("path"):
            sidecar_path = dump_path.parent / sidecar_entry["path"]
    except Exception as e:
        print(f"Warning: Failed to parse dump_index for file ingestion: {e}", file=sys.stderr)

    if sidecar_path and sidecar_path.exists():
        try:
            sidecar_data = json.loads(sidecar_path.read_text(encoding="utf-8"))
            files_list = sidecar_data.get("files", [])
            batch_files = []

            for f in files_list:
                fid = f.get("id")
                if not fid: continue

                f_repo = f.get("repo", "unknown")
                f_path = f.get("path", "")
                f_sha = f.get("sha256", "")
                f_size = f.get("size_bytes", 0)
                f_lang = f.get("language", "")

                batch_files.append((fid, f_repo, f_path, f_sha, f_size, f_lang))
                stats["ingested_files_count"] += 1

                if len(batch_files) >= batch_size:
                    c.executemany("""
                        INSERT INTO files (file_id, repo_id, path, file_sha256, size_bytes, language)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, batch_files)
                    batch_files = []

            if batch_files:
                c.executemany("""
                    INSERT INTO files (file_id, repo_id, path, file_sha256, size_bytes, language)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, batch_files)

        except Exception as e:
            print(f"Warning: Failed to ingest files from sidecar: {e}", file=sys.stderr)

    # 1. Metadata (written last to include stats)
    dump_sha = _compute_file_sha256(dump_path)
    chunk_sha = _compute_file_sha256(chunk_path)

    # Use real UTC timestamp
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

    meta_items = [
        ("schema_version", INDEX_SCHEMA_VERSION),
        ("dump_sha256", dump_sha),
        ("chunk_index_sha256", chunk_sha),
        ("created_at", now_utc),
        ("run_id", run_id),
        ("config_json", json.dumps(config_payload or {}))
    ]

    # Add stats to meta
    for k, v in stats.items():
        meta_items.append((f"ingest.{k}", str(v)))

    c.executemany("INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)", meta_items)

    conn.commit()
    conn.close()

    # Emit warning if issues found
    if stats["invalid_json_lines"] > 0 or stats["missing_chunk_id_lines"] > 0:
        msg = (f"Warning: Index ingest had issues (invalid_json={stats['invalid_json_lines']}, "
               f"missing_id={stats['missing_chunk_id_lines']}). Total lines: {stats['total_lines']}")
        print(msg, file=sys.stderr)

def verify_index(db_path: Path, dump_path: Path, chunk_path: Path) -> bool:
    """
    Verifies if the index is fresh and matches the artifacts.
    Returns True if valid, False if stale/invalid.
    """
    if not db_path.exists():
        return False

    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()

        row_dump = c.execute("SELECT value FROM index_meta WHERE key='dump_sha256'").fetchone()
        row_chunk = c.execute("SELECT value FROM index_meta WHERE key='chunk_index_sha256'").fetchone()

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
