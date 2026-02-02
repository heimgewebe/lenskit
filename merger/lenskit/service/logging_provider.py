from typing import Protocol, List, Tuple
from .jobstore import JobStore

class LogProvider(Protocol):
    def read_log_lines(self, job_id: str) -> List[str]:
        ...

    def read_log_chunk(self, job_id: str, last_line_id: int) -> List[Tuple[str, int]]:
        ...

class FileLogProvider:
    def __init__(self, job_store: JobStore):
        self.job_store = job_store

    def read_log_lines(self, job_id: str) -> List[str]:
        return self.job_store.read_log_lines(job_id)

    def read_log_chunk(self, job_id: str, last_line_id: int) -> List[Tuple[str, int]]:
        return self.job_store.read_log_chunk(job_id, last_line_id)

class MockLogProvider:
    def __init__(self, logs_map: dict):
        self.logs_map = logs_map

    def read_log_lines(self, job_id: str) -> List[str]:
        return self.logs_map.get(job_id, [])

    def read_log_chunk(self, job_id: str, last_line_id: int) -> List[Tuple[str, int]]:
        lines = self.logs_map.get(job_id, [])
        # last_line_id is 1-based index of last sent line.
        # If last_line_id is 0, we start at index 0.
        # If last_line_id is 1, we start at index 1.
        start_idx = last_line_id
        chunk = lines[start_idx:]
        return [(line, start_idx + i + 1) for i, line in enumerate(chunk)]
