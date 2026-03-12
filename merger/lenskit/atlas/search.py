import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import fnmatch

class AtlasSearch:
    def __init__(self, registry_db_path: Path):
        self.registry_db_path = registry_db_path

    def search(self,
               query: Optional[str] = None,
               machine_id: Optional[str] = None,
               root_id: Optional[str] = None,
               snapshot_id: Optional[str] = None,
               path_pattern: Optional[str] = None,
               name_pattern: Optional[str] = None,
               ext: Optional[str] = None,
               min_size: Optional[int] = None,
               max_size: Optional[int] = None,
               date_after: Optional[str] = None,
               date_before: Optional[str] = None) -> List[Dict[str, Any]]:

        # Open registry to find the appropriate snapshots
        conn = sqlite3.connect(self.registry_db_path)
        conn.row_factory = sqlite3.Row

        try:
            cur = conn.cursor()
            query_str = "SELECT * FROM snapshots WHERE status = 'complete'"
            params = []

            if machine_id:
                query_str += " AND machine_id = ?"
                params.append(machine_id)

            if root_id:
                query_str += " AND root_id = ?"
                params.append(root_id)

            if snapshot_id:
                query_str += " AND snapshot_id = ?"
                params.append(snapshot_id)

            # If snapshot not specified, we usually want to search the latest snapshot per root
            if not snapshot_id:
                # Group by root_id and get the latest
                # Just sorting and then picking the first one in code is easier for now
                query_str += " ORDER BY created_at DESC"

            cur.execute(query_str, params)
            snapshots = [dict(row) for row in cur.fetchall()]

            if not snapshot_id:
                # Keep only the latest snapshot per root
                latest_snapshots = {}
                for s in snapshots:
                    if s['root_id'] not in latest_snapshots:
                        latest_snapshots[s['root_id']] = s
                snapshots = list(latest_snapshots.values())

        finally:
            conn.close()

        results = []

        # If ext doesn't start with '.', add it to match how it's stored
        if ext and not ext.startswith('.'):
            ext = f".{ext}"

        for snap in snapshots:
            inv_ref = snap.get("inventory_ref")
            if not inv_ref:
                continue

            inv_path = Path(inv_ref)
            if not inv_path.exists():
                continue

            try:
                with open(inv_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue

                        try:
                            item = json.loads(line)

                            # Apply filters
                            if path_pattern and not fnmatch.fnmatch(item.get('rel_path', ''), path_pattern):
                                continue

                            if name_pattern and not fnmatch.fnmatch(item.get('name', ''), name_pattern):
                                continue

                            if ext and item.get('ext', '') != ext:
                                continue

                            size = item.get('size_bytes', 0)
                            if min_size is not None and size < min_size:
                                continue

                            if max_size is not None and size > max_size:
                                continue

                            mtime = item.get('mtime', '')
                            if date_after and mtime < date_after:
                                continue

                            if date_before and mtime > date_before:
                                continue

                            # Basic content/query match (search in name or path if query provided)
                            if query:
                                q_lower = query.lower()
                                name_lower = item.get('name', '').lower()
                                path_lower = item.get('rel_path', '').lower()
                                if q_lower not in name_lower and q_lower not in path_lower:
                                    continue

                            # Enrich result with snapshot context
                            result_item = dict(item)
                            result_item['machine_id'] = snap['machine_id']
                            result_item['root_id'] = snap['root_id']
                            result_item['snapshot_id'] = snap['snapshot_id']

                            results.append(result_item)

                        except (json.JSONDecodeError, KeyError):
                            pass
            except Exception:
                pass

        return results
