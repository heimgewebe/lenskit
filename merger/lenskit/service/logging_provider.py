from typing import Protocol, List, Any, Tuple
from pathlib import Path
from .jobstore import JobStore

class LogProvider(Protocol):
    def read_log_lines(self, job_id: str) -> List[str]:
        ...

    def read_log_chunk(self, job_id: str, offset: Any) -> List[Tuple[str, Any]]:
        ...

class FileLogProvider:
    def __init__(self, job_store: JobStore):
        self.job_store = job_store

    def read_log_lines(self, job_id: str) -> List[str]:
        return self.job_store.read_log_lines(job_id)

    def read_log_chunk(self, job_id: str, offset: Any) -> List[Tuple[str, Any]]:
        return self.job_store.read_log_chunk(job_id, offset)

class MockLogProvider:
    def __init__(self, logs_map: dict):
        self.logs_map = logs_map

    def read_log_lines(self, job_id: str) -> List[str]:
        return self.logs_map.get(job_id, [])

    def read_log_chunk(self, job_id: str, offset: Any) -> List[Tuple[str, Any]]:
        # Mock uses line index as offset
        if not isinstance(offset, int):
            offset = 0
        lines = self.logs_map.get(job_id, [])
        chunk = lines[offset:]
        return [(line, offset + i + 1) for i, line in enumerate(chunk)]
