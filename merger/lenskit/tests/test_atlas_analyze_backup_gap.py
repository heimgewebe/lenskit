import pytest
from pathlib import Path
from merger.lenskit.atlas.diff import _compare_file_sets

def test_compare_file_sets_semantics_for_backup_gap():
    """
    Strict semantic test proving that the file comparison logic
    maps correctly to the backup gap domains.
    """

    # Source (from) files
    source_files = {
        "doc/only_in_source.md": {"size_bytes": 100, "mtime": "2024-01-01", "is_symlink": False},
        "doc/both_unchanged.md": {"size_bytes": 200, "mtime": "2024-01-01", "is_symlink": False},
        "doc/both_changed.md": {"size_bytes": 300, "mtime": "2024-01-01", "is_symlink": False},
    }

    # Backup (to) files
    backup_files = {
        "doc/only_in_backup.md": {"size_bytes": 50, "mtime": "2024-01-01", "is_symlink": False},
        "doc/both_unchanged.md": {"size_bytes": 200, "mtime": "2024-01-01", "is_symlink": False},
        "doc/both_changed.md": {"size_bytes": 400, "mtime": "2024-01-02", "is_symlink": False}, # Changed size and mtime
    }

    new_files, removed_files, changed_files = _compare_file_sets(source_files, backup_files)

    # Prove the mapping:
    # 1. missing_in_backup -> removed_files
    # "only_in_source.md" should be missing in backup (removed from the perspective of source -> backup)
    assert removed_files == ["doc/only_in_source.md"]

    # 2. outdated_in_backup -> changed_files
    # "both_changed.md" should be outdated
    assert changed_files == ["doc/both_changed.md"]

    # 3. extraneous_in_backup -> new_files
    # "only_in_backup.md" should be extraneous
    assert new_files == ["doc/only_in_backup.md"]
