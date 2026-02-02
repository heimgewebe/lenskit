import json
import threading
import itertools
import collections
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
from typing import List, Optional, Dict, Tuple
from .models import Job, Artifact

try:
    from ..core.merge import MERGES_DIR_NAME, get_merges_dir
except ImportError:
    from merger.lenskit.core.merge import MERGES_DIR_NAME, get_merges_dir

logger = logging.getLogger(__name__)

class JobStore:
    def __init__(self, hub_path: Path):
        self.hub_path = hub_path
        self.storage_dir = self.hub_path / MERGES_DIR_NAME / ".rlens-service"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_file = self.storage_dir / "jobs.json"
        self.artifacts_file = self.storage_dir / "artifacts.json"
        self.logs_dir = self.storage_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

        self._jobs_cache: Dict[str, Job] = {}
        self._artifacts_cache: Dict[str, Artifact] = {}

        self._load()

    def _load(self):
        with self._lock:
            if self.jobs_file.exists():
                try:
                    data = json.loads(self.jobs_file.read_text(encoding="utf-8"))
                    for j in data:
                        job = Job(**j)
                        self._jobs_cache[job.id] = job
                except Exception as e:
                    print(f"Error loading jobs: {e}")

            if self.artifacts_file.exists():
                try:
                    data = json.loads(self.artifacts_file.read_text(encoding="utf-8"))
                    for a in data:
                        art = Artifact(**a)
                        self._artifacts_cache[art.id] = art
                except Exception as e:
                    print(f"Error loading artifacts: {e}")

    def _save_jobs(self):
        # Must be called under lock
        tmp_file = self.jobs_file.with_suffix(".tmp")
        data = [j.model_dump() for j in self._jobs_cache.values()]
        tmp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp_file.rename(self.jobs_file)

    def _save_artifacts(self):
        # Must be called under lock
        tmp_file = self.artifacts_file.with_suffix(".tmp")
        data = [a.model_dump() for a in self._artifacts_cache.values()]
        tmp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp_file.rename(self.artifacts_file)

    def add_job(self, job: Job):
        with self._lock:
            self._jobs_cache[job.id] = job
            self._save_jobs()

    def update_job(self, job: Job):
        with self._lock:
            self._jobs_cache[job.id] = job
            self._save_jobs()

    def append_log_line(self, job_id: str, line: str):
        with self._lock:
            p = self.logs_dir / f"{job_id}.log"
            with p.open("a", encoding="utf-8", errors="replace") as f:
                f.write(line + "\n")

    def read_log_lines(self, job_id: str) -> List[str]:
        with self._lock:
            p = self.logs_dir / f"{job_id}.log"
            try:
                if not p.exists():
                    return []
                return p.read_text(encoding="utf-8", errors="replace").splitlines()
            except FileNotFoundError:
                return []

    def read_log_chunk(self, job_id: str, last_line_id: int) -> List[Tuple[str, int]]:
        with self._lock:
            p = self.logs_dir / f"{job_id}.log"
            if not p.exists():
                return []

            try:
                # Optimized read: Skip lines without loading them into memory list
                # Use islice to skip 'last_line_id' lines efficiently
                with p.open("r", encoding="utf-8", errors="replace") as f:
                    # Defensively clamp last_line_id to 0 to avoid negative indexing issues
                    skip_count = max(0, last_line_id)

                    # Skip previous lines
                    if skip_count > 0:
                        # Consumes iterator O(skip_count) but O(1) memory.
                        # Using collections.deque with maxlen=0 is a standard idiom for consuming iterators.
                        collections.deque(itertools.islice(f, skip_count), maxlen=0)

                    # Read remaining lines
                    new_lines = []
                    current_id = last_line_id

                    for line in f:
                        current_id += 1
                        # Robustly strip CRLF (Windows) and LF (Unix)
                        new_lines.append((line.rstrip('\r\n'), current_id))

                    return new_lines

            except FileNotFoundError:
                return []
            except Exception as e:
                # Swallow exceptions to prevent SSE stream crashes.
                # Logs may be rotated/deleted/corrupted, but service must stay up.
                logger.debug("read_log_chunk failed for %s: %s", job_id, e)
                return []

    def remove_job(self, job_id: str):
        with self._lock:
            self._remove_job_internal(job_id)
            self._save_jobs()
            self._save_artifacts()

    def _remove_job_internal(self, job_id: str):
        # Internal helper, expects lock
        job = self._jobs_cache.get(job_id)
        if not job:
            return

        def _safe_unlink(base: Path, rel: str) -> None:
            """
            Best-effort deletion but never outside base directory.
            Reject absolute paths and traversal.
            """
            if not rel:
                return
            # Disallow absolute paths
            if os.path.isabs(rel):
                return
            try:
                target = (base / rel).resolve()
                base_r = base.resolve()
                # Ensure target is within base
                target.relative_to(base_r)
            except Exception:
                return
            try:
                if target.exists():
                    target.unlink()
            except Exception:
                pass

        # Remove artifacts and physical files
        for art_id in job.artifact_ids:
            art = self._artifacts_cache.get(art_id)
            if art:
                # Attempt physical deletion (best effort)
                try:
                    merges_dir = None
                    if art.params.merges_dir:
                        merges_dir = Path(art.params.merges_dir)
                    else:
                        merges_dir = get_merges_dir(Path(art.hub))

                    if merges_dir.exists():
                        for fname in art.paths.values():
                            _safe_unlink(merges_dir, fname)
                except Exception:
                    pass

                del self._artifacts_cache[art_id]

        # Remove logs
        log_p = self.logs_dir / f"{job_id}.log"
        try:
            if log_p.exists():
                log_p.unlink()
        except Exception:
            pass

        # Remove job
        if job_id in self._jobs_cache:
            del self._jobs_cache[job_id]

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs_cache.get(job_id)

    def get_all_jobs(self) -> List[Job]:
        with self._lock:
            # Sort by created_at desc
            return sorted(self._jobs_cache.values(), key=lambda x: x.created_at, reverse=True)

    def find_job_by_hash(self, content_hash: str) -> Optional[Job]:
        with self._lock:
            candidates = [j for j in self._jobs_cache.values() if j.content_hash == content_hash]
            if not candidates:
                return None

            # Priority: running/queued/canceling > succeeded/failed/canceled
            # Within priority: newest created_at

            active = [j for j in candidates if j.status in ("queued", "running", "canceling")]
            if active:
                return sorted(active, key=lambda x: x.created_at, reverse=True)[0]

            return sorted(candidates, key=lambda x: x.created_at, reverse=True)[0]

    def cleanup_jobs(self, max_jobs: int = 100, max_age_hours: int = 24):
        now = datetime.now(timezone.utc)
        limit_time = now - timedelta(hours=max_age_hours)

        with self._lock:
            to_remove = set()
            all_jobs = sorted(self._jobs_cache.values(), key=lambda x: x.created_at, reverse=True)

            # 1. Age check
            for job in all_jobs:
                try:
                    s = job.created_at
                    if s.endswith("Z"):
                        s = s[:-1] + "+00:00"
                    dt = datetime.fromisoformat(s)
                    # Handle backward compatibility for naive timestamps from old persisted jobs
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)

                    if dt < limit_time:
                        if job.status not in ("queued", "running", "canceling"):
                            to_remove.add(job.id)
                except Exception:
                    pass

            # 2. Count check
            remaining = [j for j in all_jobs if j.id not in to_remove]

            finished = [j for j in remaining if j.status not in ("queued", "running", "canceling")]
            active = [j for j in remaining if j.status in ("queued", "running", "canceling")]

            capacity = max(0, max_jobs - len(active))

            if len(finished) > capacity:
                for j in finished[capacity:]:
                    to_remove.add(j.id)

            if not to_remove:
                return

            for job_id in to_remove:
                self._remove_job_internal(job_id)

            if to_remove:
                self._save_jobs()
                self._save_artifacts()

    def add_artifact(self, artifact: Artifact):
        with self._lock:
            self._artifacts_cache[artifact.id] = artifact
            self._save_artifacts()

    def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        with self._lock:
            return self._artifacts_cache.get(artifact_id)

    def get_all_artifacts(self) -> List[Artifact]:
        with self._lock:
            return sorted(self._artifacts_cache.values(), key=lambda x: x.created_at, reverse=True)
