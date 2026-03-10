import sqlite3
import datetime
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

class AtlasRegistry:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute("PRAGMA foreign_keys = ON;")
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS machines (
                    machine_id TEXT PRIMARY KEY,
                    hostname TEXT NOT NULL,
                    labels TEXT,
                    last_seen_at TEXT
                );
                CREATE TABLE IF NOT EXISTS roots (
                    root_id TEXT PRIMARY KEY,
                    machine_id TEXT NOT NULL,
                    root_kind TEXT NOT NULL,
                    root_value TEXT NOT NULL,
                    label TEXT,
                    FOREIGN KEY(machine_id) REFERENCES machines(machine_id)
                );
                CREATE TABLE IF NOT EXISTS snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    machine_id TEXT NOT NULL,
                    root_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    scan_config_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    inventory_ref TEXT,
                    dirs_ref TEXT,
                    summary_ref TEXT,
                    content_ref TEXT,
                    topology_ref TEXT,
                    hotspots_ref TEXT,
                    workspaces_ref TEXT,
                    FOREIGN KEY(machine_id) REFERENCES machines(machine_id),
                    FOREIGN KEY(root_id) REFERENCES roots(root_id)
                );
            """)

    def register_machine(self, machine_id: str, hostname: str, labels: Optional[List[str]] = None):
        labels_json = json.dumps(labels) if labels else None
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.conn:
            self.conn.execute("""
                INSERT INTO machines (machine_id, hostname, labels, last_seen_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(machine_id) DO UPDATE SET
                    hostname=excluded.hostname,
                    labels=excluded.labels,
                    last_seen_at=excluded.last_seen_at
            """, (machine_id, hostname, labels_json, now))

    def get_machine(self, machine_id: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM machines WHERE machine_id = ?", (machine_id,))
        row = cur.fetchone()
        if not row:
            return None
        res = dict(row)
        res['labels'] = json.loads(res['labels']) if res['labels'] else None
        return res

    def list_machines(self) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM machines")
        machines = []
        for row in cur.fetchall():
            res = dict(row)
            res['labels'] = json.loads(res['labels']) if res['labels'] else None
            machines.append(res)
        return machines

    def register_root(self, root_id: str, machine_id: str, root_kind: str, root_value: str, label: Optional[str] = None):
        with self.conn:
            self.conn.execute("""
                INSERT INTO roots (root_id, machine_id, root_kind, root_value, label)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(root_id) DO UPDATE SET
                    machine_id=excluded.machine_id,
                    root_kind=excluded.root_kind,
                    root_value=excluded.root_value,
                    label=excluded.label
            """, (root_id, machine_id, root_kind, root_value, label))

    def get_root(self, root_id: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM roots WHERE root_id = ?", (root_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def list_roots(self) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM roots")
        return [dict(row) for row in cur.fetchall()]

    def create_snapshot(self, snapshot_id: str, machine_id: str, root_id: str, scan_config_hash: str, status: str):
        now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
        with self.conn:
            self.conn.execute("""
                INSERT INTO snapshots (snapshot_id, machine_id, root_id, created_at, scan_config_hash, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (snapshot_id, machine_id, root_id, now, scan_config_hash, status))

    def update_snapshot_status(self, snapshot_id: str, status: str):
        with self.conn:
            self.conn.execute("""
                UPDATE snapshots SET status = ? WHERE snapshot_id = ?
            """, (status, snapshot_id))

    def update_snapshot_artifacts(self, snapshot_id: str, artifacts: Dict[str, str]):
        set_clauses = []
        params = []
        for key in ["inventory", "dirs", "summary", "content", "topology", "hotspots", "workspaces"]:
            if key in artifacts:
                set_clauses.append(f"{key}_ref = ?")
                params.append(artifacts[key])

        if not set_clauses:
            return

        params.append(snapshot_id)
        query = f"UPDATE snapshots SET {', '.join(set_clauses)} WHERE snapshot_id = ?"
        with self.conn:
            self.conn.execute(query, params)

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM snapshots WHERE snapshot_id = ?", (snapshot_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def list_snapshots(self) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM snapshots ORDER BY created_at DESC")
        return [dict(row) for row in cur.fetchall()]
