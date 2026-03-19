import sqlite3
from pathlib import Path
from merger.lenskit.cli.stale_check import check_stale_index, _compute_file_sha256

def test_stale_check_with_special_characters_in_path(tmp_path):
    # This test ensures that paths with '?' (which could be used for URI injection)
    # are handled correctly by the stale check logic.

    # We create a directory with '?' in its name.
    special_dir = tmp_path / "path_with_?_mark"
    special_dir.mkdir()

    base_name = "test_run"
    index_path = special_dir / f"{base_name}.chunk_index.index.sqlite"
    dump_path = special_dir / f"{base_name}.dump_index.json"

    # Create a valid SQLite DB at that path
    with sqlite3.connect(str(index_path)) as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE index_meta (key TEXT PRIMARY KEY, value TEXT)")
        c.execute("INSERT INTO index_meta (key, value) VALUES ('canonical_dump_index_sha256', 'some_hash')")
        conn.commit()

    # Create the dump file
    dump_path.write_text("dump content", encoding="utf-8")
    actual_hash = _compute_file_sha256(dump_path)

    # Update DB with correct hash
    with sqlite3.connect(str(index_path)) as conn:
        c = conn.cursor()
        c.execute("UPDATE index_meta SET value=? WHERE key='canonical_dump_index_sha256'", (actual_hash,))
        conn.commit()

    # If the injection vulnerability was present, _get_sha_from_db would likely fail
    # to connect or query the DB because '?' would start a query string in the URI.

    # Result should be False (not stale) because hashes match and DB is readable.
    result = check_stale_index(index_path, stale_policy="fail")

    assert result is False
