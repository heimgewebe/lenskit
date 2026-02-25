import hashlib
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class Chunk:
    chunk_id: str
    file_id: str
    byte_offset_start: int
    byte_offset_end: int
    line_start: int
    line_end: int
    content_sha256: str
    size_bytes: int
    # Optional symbols/metadata can be added here
    symbols: Optional[List[str]] = None

class Chunker:
    def __init__(self, min_size: int = 2048, max_size: int = 8192, min_lines: int = 200, max_lines: int = 400):
        """
        Initialize Chunker.
        Note: min_size and min_lines are currently unused and reserved for future heuristics.
        """
        self.min_size = min_size
        self.max_size = max_size
        self.min_lines = min_lines
        self.max_lines = max_lines

    def chunk_file(self, file_id: str, content: str, byte_offset_base: int = 0, file_path: Optional[str] = None) -> List[Chunk]:
        """
        Splits content into chunks based on lines and size constraints.
        This is a simple line-based chunker that tries to respect boundaries.

        file_path is optional but recommended for stable ID generation.
        """
        chunks = []
        lines = content.splitlines(keepends=True)

        current_chunk_lines = []
        current_chunk_size = 0
        chunk_start_line = 1
        chunk_start_byte = byte_offset_base

        current_byte_offset = byte_offset_base

        for i, line in enumerate(lines):
            line_bytes = len(line.encode('utf-8'))

            # Check if adding this line would exceed max size or max lines
            # But only if we have at least something in the chunk
            if current_chunk_lines and (
                (current_chunk_size + line_bytes > self.max_size) or
                (len(current_chunk_lines) >= self.max_lines)
            ):
                # Finalize current chunk
                self._finalize_chunk(chunks, file_id, current_chunk_lines, chunk_start_line, chunk_start_byte, file_path=file_path)

                # Reset for next chunk
                chunk_start_line = i + 1
                chunk_start_byte = current_byte_offset
                current_chunk_lines = []
                current_chunk_size = 0

            current_chunk_lines.append(line)
            current_chunk_size += line_bytes
            current_byte_offset += line_bytes

            # Check if we should split based on min size/lines logic (e.g. natural breaks)
            # For now, we greedily fill up to max, unless we hit a very logical break point?
            # The prompt asks for "stable chunks". Greedily filling to max or range is stable enough for now.
            # We could add heuristic splitting later.

        # Finalize last chunk
        if current_chunk_lines:
            self._finalize_chunk(chunks, file_id, current_chunk_lines, chunk_start_line, chunk_start_byte, file_path=file_path)

        return chunks

    def _finalize_chunk(self, chunks: List[Chunk], file_id: str, lines: List[str], start_line: int, start_byte: int, file_path: Optional[str] = None):
        content = "".join(lines)
        content_bytes = content.encode('utf-8')
        size = len(content_bytes)
        sha256 = hashlib.sha256(content_bytes).hexdigest()

        # Deterministic Chunk ID (v2.4 Spec): sha1(file_path + start_line + content_hash)
        # Stable at identical content and position.
        # If file_path is not provided, we fall back to file_id (which is usually FILE:f_...).
        path_key = file_path if file_path else file_id

        # We construct the input string as requested
        # Note: start_line is 1-based index.
        chunk_hash_input = f"{path_key}{start_line}{sha256}".encode('utf-8')
        chunk_id = hashlib.sha1(chunk_hash_input).hexdigest()

        chunks.append(Chunk(
            chunk_id=chunk_id,
            file_id=file_id,
            byte_offset_start=start_byte,
            byte_offset_end=start_byte + size,
            line_start=start_line,
            line_end=start_line + len(lines) - 1,
            content_sha256=sha256,
            size_bytes=size
        ))
