import json
import threading
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

VALID_ARTIFACT_TYPES = frozenset({"query_trace", "context_bundle", "agent_query_session"})

_STORE_FILENAME = "query_artifacts.json"


class QueryArtifactStore:
    """Persistent store for query runtime artifacts.

    Artifacts (query_trace, context_bundle, agent_query_session) are produced
    ephemerally during execute_query(). This store assigns IDs and persists
    them so they can be retrieved via artifact_lookup without re-executing any
    query.

    ID stability: IDs are stable within this store instance for the lifetime
    of the underlying JSON file.  They are not guaranteed to be resolvable
    after the store location changes (e.g. different merges_dir).

    Known limitations (open, not in scope for this PR):
    - No retention/GC policy: the store grows unbounded.
    - No federation artifact support.
    - No raw-vs-projected artifact distinction (context_bundle is stored in
      the projected API form, not the internal execute_query() form).

    Storage format: JSON list at {storage_dir}/query_artifacts.json.
    All writes are atomic (tmp-rename).
    """

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._store_file = self.storage_dir / _STORE_FILENAME
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self._store_file.exists():
                return
            try:
                data = json.loads(self._store_file.read_text(encoding="utf-8"))
                for entry in data:
                    self._cache[entry["id"]] = entry
            except Exception as e:
                logger.error("Failed to load query artifacts from %s: %s", self._store_file, e)

    def _save(self) -> None:
        tmp = self._store_file.with_suffix(".tmp")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(
            json.dumps(list(self._cache.values()), indent=2),
            encoding="utf-8",
        )
        tmp.replace(self._store_file)

    def store(
        self,
        artifact_type: str,
        data: Dict[str, Any],
        provenance: Dict[str, Any],
        run_id: Optional[str] = None,
    ) -> str:
        """Store a query artifact and return its stable artifact_id.

        Args:
            artifact_type: One of "query_trace", "context_bundle", "agent_query_session".
            data: The artifact payload (must be JSON-serialisable).
            provenance: Dict with at minimum "source_query" and "timestamp".
            run_id: Optional correlation ID linking artifacts from the same execution.

        Returns:
            A stable artifact_id string (e.g. "qart-<hex>").
        """
        if artifact_type not in VALID_ARTIFACT_TYPES:
            raise ValueError(
                f"Invalid artifact_type {artifact_type!r}. "
                f"Must be one of: {sorted(VALID_ARTIFACT_TYPES)}"
            )

        artifact_id = f"qart-{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc).isoformat()

        prov = dict(provenance)
        if run_id is not None:
            prov.setdefault("run_id", run_id)
        prov.setdefault("run_id", None)

        entry: Dict[str, Any] = {
            "id": artifact_id,
            "artifact_type": artifact_type,
            "data": data,
            "provenance": prov,
            "created_at": now,
        }

        with self._lock:
            self._cache[artifact_id] = entry
            self._save()

        return artifact_id

    def get(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """Return the stored entry for artifact_id, or None if not found."""
        with self._lock:
            return self._cache.get(artifact_id)

    def get_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return sorted(
                self._cache.values(),
                key=lambda e: e.get("created_at", ""),
                reverse=True,
            )
