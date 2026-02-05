import os
import logging
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Pattern, Union, Tuple
from datetime import datetime, timezone
import fnmatch
import re

# Attempt to import is_probably_text from core to avoid duplication
try:
    from ..core.merge import is_probably_text
except ImportError:
    # Fallback implementation if core is not accessible
    # Configurable text detection limit (aligned with core's 20MB)
    TEXT_DETECTION_MAX_BYTES = 20 * 1024 * 1024

    def is_probably_text(path: Path, size: int) -> bool:
        TEXT_EXTENSIONS = {
            ".md", ".txt", ".py", ".rs", ".ts", ".js", ".json", ".yml", ".yaml",
            ".sh", ".html", ".css", ".xml", ".csv", ".log", ".lock", ".gitignore",
            ".toml", ".ini", ".conf", ".dockerfile", "dockerfile", ".bat", ".cmd"
        }
        if path.suffix.lower() in TEXT_EXTENSIONS or path.name.lower() in TEXT_EXTENSIONS:
            return True
        if size > TEXT_DETECTION_MAX_BYTES:
            return False
        try:
            with path.open("rb") as f:
                chunk = f.read(4096)
                if not chunk: return True
                return b"\x00" not in chunk
        except OSError:
            return False

logger = logging.getLogger(__name__)

class AtlasScanner:
    def __init__(self, root: Path, max_depth: int = 6, max_entries: int = 200000,
                 exclude_globs: List[str] = None, inventory_strict: bool = False):
        self.root = root
        self.max_depth = max_depth
        self.max_entries = max_entries
        self.inventory_strict = inventory_strict

        if self.inventory_strict:
            # Minimal excludes for strict inventory: only git and venv
            default_excludes = ["**/.git", "**/.venv"]
        else:
            default_excludes = ["**/.git", "**/node_modules", "**/.venv", "**/__pycache__", "**/.cache"]

        self.exclude_globs = exclude_globs if exclude_globs is not None else default_excludes
        self._exclude_patterns = self._build_exclude_patterns(self.exclude_globs)
        self._exclude_regex = self._compile_exclude_regex(self._exclude_patterns)
        self.stats = {
            "total_files": 0,
            "total_dirs": 0,
            "total_bytes": 0,
            "start_time": None,
            "end_time": None,
            "duration_seconds": 0,
            "extensions": {},
            "top_dirs": [],  # List of {"path": str, "bytes": int}
            "repo_nodes": [], # List of paths that look like git repos
            "active_excludes": self.exclude_globs,
            "truncated": {
                "max_entries": self.max_entries,
                "hit": False,
                "files_seen": 0,
                "dirs_seen": 0,
                "depth_limit_hit": False,
                "reason": None
            }
        }
        self.tree = {} # Nested dict structure representing the tree

    @staticmethod
    def _build_exclude_patterns(globs: List[str]) -> List[str]:
        patterns = []
        seen = set()
        for glob in globs:
            # Normalize globs
            normalized = str(glob).replace("\\", "/")

            # Generate base candidates (original + root-stripped if starts with **/)
            candidates_set = {normalized}
            if normalized.startswith("**/"):
                candidates_set.add(normalized[3:])

            # For each candidate, ensure we have both base and "/**" version
            expanded_candidates = set()
            for cand in candidates_set:
                expanded_candidates.add(cand)
                if cand.endswith("/**"):
                    expanded_candidates.add(cand[:-3])
                else:
                    expanded_candidates.add(f"{cand}/**")

            for candidate in sorted(expanded_candidates):
                if candidate and candidate not in seen:
                    seen.add(candidate)
                    patterns.append(candidate)
        return patterns

    @staticmethod
    def _compile_exclude_regex(patterns: List[str]) -> Pattern:
        if not patterns:
            return re.compile(r"(?!x)x") # Matches nothing

        # Check if filesystem is case-insensitive to determine regex flags
        is_case_insensitive = os.path.normcase("A") == os.path.normcase("a")
        flags = re.IGNORECASE if is_case_insensitive else 0

        regex_parts = []
        for pat in patterns:
            # Ensure pattern uses forward slashes (already done in _build_exclude_patterns, but explicitly safe)
            if os.sep != "/":
                pat = pat.replace(os.sep, "/")

            # fnmatch.translate converts glob to regex (e.g., *.txt -> (?s:.*\.txt)\Z)
            # We join them with OR
            regex_parts.append(fnmatch.translate(pat))

        combined = "|".join(regex_parts)
        return re.compile(combined, flags)

    def _is_excluded(self, path: Union[Path, str]) -> bool:
        # Check against globs
        # We match relative path from root
        if isinstance(path, Path):
            try:
                rel_path = path.relative_to(self.root)
            except ValueError:
                return True # Should not happen if walking from root
            str_path = rel_path.as_posix()
        else:
            # Assume string is already relative path. Ensure POSIX slashes.
            str_path = path.replace("\\", "/")

        if self._exclude_regex.fullmatch(str_path):
            return True
        return False

    def scan(self, inventory_file: Optional[Path] = None, dirs_inventory_file: Optional[Path] = None) -> Dict[str, Any]:
        """
        Scans the directory structure.

        Args:
            inventory_file: Optional path to write a JSONL inventory of all files.
            dirs_inventory_file: Optional path to write a JSONL inventory of all directories.
        """
        self.stats["start_time"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        start_ts = time.time()

        current_entries = 0
        depth_limit_hit = False

        # Prepare inventory writers
        inv_f = None
        dirs_inv_f = None
        try:
            if inventory_file:
                inv_f = inventory_file.open("w", encoding="utf-8")
            if dirs_inventory_file:
                dirs_inv_f = dirs_inventory_file.open("w", encoding="utf-8")
        except OSError as e:
            logger.error(f"Failed to open inventory files: {e}")

        dir_sizes = {} # path -> size

        try:
            for root, dirs, files in os.walk(self.root, topdown=True):
                current_root = Path(root)

                # Calculate relative path string once
                try:
                    rel_path_obj = current_root.relative_to(self.root)
                except ValueError:
                    # Should not happen
                    dirs[:] = []
                    continue

                rel_path_str = rel_path_obj.as_posix()

                # Check exclusions for current root (prune traversal)
                if self._is_excluded(rel_path_str):
                    dirs[:] = []
                    continue

                depth = len(rel_path_obj.parts) if rel_path_str != "." else 0

                if depth > self.max_depth:
                    dirs[:] = []
                    depth_limit_hit = True
                    continue

                # Check for .git to mark repo node
                if ".git" in dirs:
                    self.stats["repo_nodes"].append(rel_path_str)
                    # Don't recurse into .git
                    dirs.remove(".git")

                # Pre-calculate prefix for children
                prefix = "" if rel_path_str == "." else rel_path_str + "/"

                # Filter dirs in-place (Pruning)
                # We must check if the dir ITSELF is excluded to prune it from walk
                kept_dirs = []
                for d in dirs:
                    # Construct relative path string for child directory
                    d_rel = prefix + d

                    if self._is_excluded(d_rel):
                        continue
                    kept_dirs.append(d)
                dirs[:] = kept_dirs

                dir_bytes = 0

                # Filter files for this directory
                # Store Tuple[str, str] -> (filename, relative_path)
                kept_files: List[Tuple[str, str]] = []
                for f in files:
                    # Construct relative path string for file
                    f_rel = prefix + f

                    if not self._is_excluded(f_rel):
                        kept_files.append((f, f_rel))

                # Directory Inventory
                if dirs_inv_f:
                    entry = {
                        "rel_path": rel_path_str,
                        "depth": depth,
                        "n_files": len(kept_files),
                        "n_dirs": len(dirs),
                        # bytes will be populated post-loop or via separate logic?
                        # For pure inventory, structure is key.
                        # We can't know recursive bytes here yet.
                        "mtime": datetime.fromtimestamp(current_root.stat().st_mtime, timezone.utc).isoformat().replace('+00:00', 'Z')
                    }
                    dirs_inv_f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

                self.stats["truncated"]["dirs_seen"] += 1

                for f, f_rel in kept_files:
                    f_path = current_root / f
                    # Exclusion check already done

                    current_entries += 1
                    self.stats["truncated"]["files_seen"] = current_entries

                    if current_entries > self.max_entries:
                        self.stats["truncated"]["hit"] = True
                        self.stats["truncated"]["reason"] = "max_entries"
                        # Reset files_seen to max_entries to reflect "stop at limit" contract
                        self.stats["truncated"]["files_seen"] = self.max_entries
                        break

                    try:
                        stat = f_path.stat()
                        size = stat.st_size
                        mtime = stat.st_mtime
                        ext = f_path.suffix.lower()
                        is_sym = f_path.is_symlink()

                        self.stats["total_files"] += 1
                        self.stats["total_bytes"] += size
                        self.stats["extensions"][ext] = self.stats["extensions"].get(ext, 0) + 1

                        dir_bytes += size

                        # Inventory Output
                        if inv_f:
                            is_txt = is_probably_text(f_path, size)
                            # Use reused relative path string
                            entry = {
                                "rel_path": f_rel,
                                "name": f,
                                "ext": ext,
                                "size_bytes": size,
                                "mtime": datetime.fromtimestamp(mtime, timezone.utc).isoformat().replace('+00:00', 'Z'),
                                "is_text": is_txt,
                                "is_symlink": is_sym
                            }
                            inv_f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

                    except OSError:
                        continue

                if self.stats["truncated"]["hit"]:
                    break

                self.stats["total_dirs"] += 1
                dir_sizes[rel_path_str] = dir_bytes

        finally:
            if inv_f: inv_f.close()
            if dirs_inv_f: dirs_inv_f.close()

        # Update stats
        if depth_limit_hit:
             self.stats["truncated"]["depth_limit_hit"] = True
             if not self.stats["truncated"]["hit"]:
                 self.stats["truncated"]["hit"] = True
                 self.stats["truncated"]["reason"] = "max_depth"

        # Calculate Duration
        self.stats["end_time"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        self.stats["duration_seconds"] = time.time() - start_ts

        # Find Top Dirs (Hotspots) - simplistic aggregation
        all_paths = sorted(dir_sizes.keys(), key=lambda p: len(Path(p).parts), reverse=True)
        recursive_sizes = dir_sizes.copy()

        for p_str in all_paths:
            if p_str == ".":
                continue
            p = Path(p_str)
            parent = str(p.parent)
            if parent == ".":
                pass

            if parent in recursive_sizes:
                recursive_sizes[parent] += recursive_sizes[p_str]

        sorted_dirs = sorted(recursive_sizes.items(), key=lambda x: x[1], reverse=True)
        self.stats["top_dirs"] = [{"path": p, "bytes": s} for p, s in sorted_dirs[:50]]

        # Add inventory metadata to stats if file was generated
        if inventory_file:
            self.stats["inventory_file"] = str(inventory_file.resolve())
        if dirs_inventory_file:
            self.stats["dirs_inventory_file"] = str(dirs_inventory_file.resolve())

        self.stats["inventory_strict"] = self.inventory_strict

        return {
            "root": str(self.root),
            "stats": self.stats,
        }

    def merge_folder(self, folder_rel_path: str, output_file: Path,
                     recursive: bool = False, max_files: int = 1000, max_bytes: int = 10 * 1024 * 1024) -> Dict[str, Any]:
        """
        Situative Folder Merge: Merges all text files in a specific folder into one file.

        Args:
            folder_rel_path: Relative path to folder to merge.
            output_file: Path to write merged content.
            recursive: Whether to include subdirectories.
            max_files: Safety limit for number of files.
            max_bytes: Safety limit for total merged size.
        """
        target_dir = (self.root / folder_rel_path).resolve()

        try:
            target_dir.relative_to(self.root.resolve())
        except ValueError:
             raise ValueError(f"Target folder {folder_rel_path} is outside of root directory.")

        if not target_dir.exists() or not target_dir.is_dir():
            raise ValueError(f"Folder not found: {folder_rel_path}")

        files_merged = []
        files_skipped = []
        total_merged_bytes = 0
        file_count = 0

        # Gather candidates
        candidates = []
        if recursive:
            for root, dirs, files in os.walk(target_dir):
                # Apply same excludes? Or raw merge?
                # User said "situative folder merge... roh...".
                # Usually explicit merge implies "I want this folder".
                # But we should probably respect excludes to avoid merging .git etc.

                # Exclude directories from traversal
                # Similar logic to scan() pruning
                current_root = Path(root)
                if self._is_excluded(current_root):
                    dirs[:] = []
                    continue

                kept_dirs = []
                for d in dirs:
                    d_path = current_root / d
                    if not self._is_excluded(d_path):
                        kept_dirs.append(d)
                dirs[:] = kept_dirs

                for f in files:
                    candidates.append(Path(root) / f)
        else:
            for item in target_dir.iterdir():
                if item.is_file():
                    candidates.append(item)

        # Deterministic sort
        # Sort by relative path to target_dir for stability
        candidates.sort(key=lambda p: str(p.relative_to(target_dir)).lower())

        limit_hit_reason = None

        with output_file.open("w", encoding="utf-8") as out:
            out.write(f"# Atlas Folder Merge: {folder_rel_path}\n")
            out.write(f"# Generated: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}\n")
            out.write(f"# Recursive: {recursive}\n\n")

            for f_path in candidates:
                # Check exclusion again for the file path
                if self._is_excluded(f_path):
                    continue

                if file_count >= max_files:
                    limit_hit_reason = "max_files"
                    break

                if total_merged_bytes >= max_bytes:
                    limit_hit_reason = "max_bytes"
                    break

                rel_path = f_path.relative_to(self.root).as_posix()
                try:
                    size = f_path.stat().st_size
                    if is_probably_text(f_path, size):
                        out.write(f"===== FILE: {rel_path} =====\n")
                        try:
                            content = f_path.read_text(encoding="utf-8", errors="replace")
                            out.write(content)
                            total_merged_bytes += len(content.encode("utf-8")) # Rough estimate
                        except Exception as e:
                            out.write(f"[Error reading file: {e}]\n")
                        out.write("\n\n")
                        files_merged.append(rel_path)
                        file_count += 1
                    else:
                        files_skipped.append({"path": rel_path, "reason": "binary/non-text"})
                except OSError as e:
                    files_skipped.append({"path": rel_path, "reason": f"fs_error: {e}"})

            if limit_hit_reason:
                out.write(f"\n===== MERGE TRUNCATED: {limit_hit_reason} reached =====\n")

            if files_skipped:
                out.write("\n===== SKIPPED FILES =====\n")
                for item in files_skipped:
                    out.write(f"- {item['path']} ({item['reason']})\n")

        return {
            "merged": files_merged,
            "skipped": files_skipped,
            "output_file": str(output_file),
            "truncated": limit_hit_reason
        }

def render_atlas_md(atlas_data: Dict[str, Any]) -> str:
    stats = atlas_data["stats"]
    root = atlas_data.get("root", "Unknown")

    lines = []
    lines.append(f"# 🗺️ Atlas: {root}")
    lines.append(f"Generated: {stats.get('end_time')} (Duration: {stats.get('duration_seconds'):.2f}s)")
    lines.append("")

    if stats.get("inventory_file"):
        lines.append(f"**Inventory (Files):** `{Path(stats.get('inventory_file')).name}`")
    if stats.get("dirs_inventory_file"):
        lines.append(f"**Inventory (Dirs):** `{Path(stats.get('dirs_inventory_file')).name}`")

    if stats.get("inventory_strict"):
        lines.append("**Mode:** Strict Inventory (minimal excludes).")
    lines.append("")

    # Truncation Warning
    trunc = stats.get("truncated", {})
    if trunc.get("hit"):
        lines.append(f"⚠️ **SCAN TRUNCATED**: {trunc.get('reason')}")
        lines.append(f"  - Files seen: {trunc.get('files_seen')}")
        lines.append(f"  - Limit: {trunc.get('max_entries')}")
        if trunc.get("depth_limit_hit"):
            lines.append("  - Depth limit hit: Yes")
        lines.append("")

    # Transparency on Excludes
    if stats.get("active_excludes"):
        lines.append("**Active Excludes:**")
        for ex in sorted(stats["active_excludes"]):
            lines.append(f"- `{ex}`")
        lines.append("")

    lines.append("## 📊 Overview")
    lines.append(f"- **Total Directories:** {stats.get('total_dirs')}")
    lines.append(f"- **Total Files:** {stats.get('total_files')}")
    lines.append(f"- **Total Size:** {stats.get('total_bytes') / (1024*1024):.2f} MB")
    lines.append("")

    lines.append("## 📁 Top Folders (Hotspots)")
    lines.append("| Path | Size (MB) |")
    lines.append("|---|---|")
    for d in stats.get("top_dirs", [])[:20]:
        mb = d['bytes'] / (1024*1024)
        lines.append(f"| `{d['path']}` | {mb:.2f} |")
    lines.append("")

    lines.append("## 🏷️ File Types")
    lines.append("| Extension | Count |")
    lines.append("|---|---|")
    # Sort extensions by count
    sorted_exts = sorted(stats.get("extensions", {}).items(), key=lambda x: x[1], reverse=True)
    for ext, count in sorted_exts[:20]:
        lines.append(f"| `{ext or '(no ext)'}` | {count} |")
    lines.append("")

    lines.append("## 📍 Git Repositories")
    repos = stats.get("repo_nodes", [])
    if repos:
        for r in sorted(repos):
            lines.append(f"- `{r}`")
    else:
        lines.append("_No git repositories found in scan scope._")

    return "\n".join(lines)
