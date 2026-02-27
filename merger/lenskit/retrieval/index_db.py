"""
Core implementation of SQLite schema and index builder.
"""

import sqlite3
import json
import hashlib
import datetime
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
    create_schema(conn)
    c = conn.cursor()

    # 1. Metadata
    dump_sha = _compute_file_sha256(dump_path)
    chunk_sha = _compute_file_sha256(chunk_path)

    # Use real UTC timestamp
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

    meta_items = [
        ("schema_version", INDEX_SCHEMA_VERSION),
        ("dump_sha256", dump_sha),
        ("chunk_index_sha256", chunk_sha),
        ("created_at", now_utc),
        ("config_json", json.dumps(config_payload or {}))
    ]

    c.executemany("INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)", meta_items)

    # 2. Ingest Chunks
    batch_size = 500
    batch_chunks = []
    batch_fts = []

    with chunk_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue

            cid = chunk.get("chunk_id")
            if not cid: continue

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

    conn.commit()
    conn.close()

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
