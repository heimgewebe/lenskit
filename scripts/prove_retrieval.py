import json
from pathlib import Path
import tempfile
import sys
import os
import subprocess

from merger.lenskit.core.merge import write_reports_v2, scan_repo, ExtrasConfig
from merger.lenskit.cli import cmd_index, cmd_query, cmd_eval

def test_retrieval_stack_integration():
    """
    Integration test proving the full retrieval stack:
    Scan -> Merge -> Index (with new files table) -> Query -> Eval
    """
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        hub = tmp_dir / "hub"
        hub.mkdir()

        repo_name = "test-repo"
        repo_root = hub / repo_name
        repo_root.mkdir()

        # Create some files
        (repo_root / "src").mkdir()
        (repo_root / "src" / "main.py").write_text("def main():\n    print('Hello Index')\n", encoding="utf-8")
        (repo_root / "README.md").write_text("# Test Repo\nThis is a test.\n", encoding="utf-8")

        # 1. Generate Artifacts (Dump + Chunk + Sidecar)
        merges_dir = tmp_dir / "merges"
        merges_dir.mkdir()

        summary = scan_repo(repo_root, calculate_md5=True)
        extras = ExtrasConfig(json_sidecar=True)

        artifacts = write_reports_v2(
            merges_dir=merges_dir,
            hub=hub,
            repo_summaries=[summary],
            detail="max",
            mode="gesamt",
            max_bytes=0,
            plan_only=False,
            output_mode="dual",
            extras=extras,
            generator_info={"name": "test-stack", "platform": "test"}
        )

        dump_path = artifacts.dump_index
        chunk_path = artifacts.chunk_index
        index_path = merges_dir / "test.index.sqlite"

        assert dump_path and dump_path.exists()
        assert chunk_path and chunk_path.exists()

        # 2. Build Index (CLI simulation)
        # Using subprocess to test CLI entry point or direct call to cmd_index
        # Direct call is safer for test environment without installing package

        class IndexArgs:
            dump = str(dump_path)
            chunk_index = str(chunk_path)
            out = str(index_path)
            rebuild = True
            verify = False

        ret = cmd_index.run_index(IndexArgs())
        assert ret == 0, "Index build failed"
        assert index_path.exists()

        # 3. Verify Files Table Population (New Feature)
        import sqlite3
        conn = sqlite3.connect(str(index_path))
        c = conn.cursor()

        # Check schema
        c.execute("PRAGMA table_info(files)")
        cols = {row[1] for row in c.fetchall()}
        assert "file_id" in cols
        assert "repo_id" in cols
        assert "file_sha256" in cols
        assert "language" in cols

        # Check data
        c.execute("SELECT count(*) FROM files")
        count = c.fetchone()[0]
        assert count == 2, f"Expected 2 files indexed, found {count}"

        c.execute("SELECT path, language FROM files WHERE path LIKE '%main.py%'")
        row = c.fetchone()
        assert row
        assert row[0].endswith("src/main.py")
        assert row[1] == "python"

        # Check run_id in meta
        c.execute("SELECT value FROM index_meta WHERE key='run_id'")
        run_id_row = c.fetchone()
        assert run_id_row, "run_id missing in index_meta"
        assert len(run_id_row[0]) > 0

        conn.close()

        # 4. Run Query (Sanity)
        class QueryArgs:
            index = str(index_path)
            q = "Hello"
            k = 5
            repo = None
            path = None
            ext = None
            layer = None
            emit = "json"

        # Capture stdout
        from io import StringIO
        import sys
        old_stdout = sys.stdout
        sys.stdout = capture = StringIO()

        try:
            ret = cmd_query.run_query(QueryArgs())
            sys.stdout = old_stdout
            assert ret == 0
            output = json.loads(capture.getvalue())

            if output["count"] == 0:
                print("DEBUG: Query failed. Inspecting DB...", file=sys.stderr)
                conn = sqlite3.connect(str(index_path))
                c = conn.cursor()
                print("DEBUG: Chunks FTS content:", file=sys.stderr)
                for row in c.execute("SELECT * FROM chunks_fts"):
                    print(row, file=sys.stderr)
                conn.close()

            assert output["count"] >= 1
            assert output["results"][0]["path"].endswith("main.py")
        finally:
            sys.stdout = old_stdout

        print("Retrieval Stack Verification: SUCCESS")

if __name__ == "__main__":
    test_retrieval_stack_integration()
