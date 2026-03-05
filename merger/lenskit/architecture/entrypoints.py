import ast
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

def extract_entrypoints(repo_root: Path) -> List[Dict[str, Any]]:
    """
    Scans a repository to find python entrypoints.
    Returns a sorted list of entrypoints conforming to entrypoints.v1 schema.
    """
    entrypoints = []

    # Sort files to ensure deterministic iteration
    for root, dirs, files in sorted(os.walk(repo_root)):
        # Exclude common directories to speed up search
        dirs[:] = sorted([d for d in dirs if d not in (".git", "venv", ".venv", "__pycache__", "node_modules", "build", "dist")])

        for file in sorted(files):
            if not file.endswith(".py"):
                continue

            file_path = Path(root) / file
            rel_path = file_path.relative_to(repo_root).as_posix()

            # Heuristic 1: __main__.py files are module_main entrypoints
            if file == "__main__.py":
                entrypoints.append({
                    "id": f"module_main_{rel_path.replace('/', '_').replace('.', '_')}",
                    "type": "module_main",
                    "path": rel_path,
                    "evidence_level": "S0",
                    "evidence": {
                        "source_path": rel_path,
                        "extract": "__main__.py file detected"
                    }
                })
                # Don't continue because a __main__.py could ALSO have an if __name__ == "__main__": block

            # Heuristic 2: Check for `if __name__ == "__main__":` block via AST
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                has_main_block = False
                main_block_lineno = None

                for node in ast.walk(tree):
                    if isinstance(node, ast.If):
                        # Check if test is `__name__ == '__main__'`
                        test = node.test
                        if isinstance(test, ast.Compare):
                            if len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq):
                                left = test.left
                                right = test.comparators[0]

                                is_name_main = False
                                if isinstance(left, ast.Name) and left.id == "__name__":
                                    if isinstance(right, ast.Constant) and right.value == "__main__":
                                        is_name_main = True

                                if isinstance(right, ast.Name) and right.id == "__name__":
                                    if isinstance(left, ast.Constant) and left.value == "__main__":
                                        is_name_main = True

                                if is_name_main:
                                    has_main_block = True
                                    main_block_lineno = node.lineno
                                    break

                if has_main_block:
                    entrypoints.append({
                        "id": f"cli_{rel_path.replace('/', '_').replace('.', '_')}",
                        "type": "cli",
                        "path": rel_path,
                        "evidence_level": "S1",
                        "evidence": {
                            "source_path": rel_path,
                            "start_line": main_block_lineno,
                            "extract": "if __name__ == '__main__': block detected"
                        }
                    })

            except Exception as e:
                # Silently ignore parsing errors or unreadable files (e.g. invalid utf-8 or syntax errors)
                continue

    # Sort the entrypoints deterministically by ID to ensure stable output
    return sorted(entrypoints, key=lambda x: x["id"])

def generate_entrypoints_document(repo_root: Path, run_id: str, canonical_sha256: str) -> Dict[str, Any]:
    """
    Generates the full entrypoints.v1 schema compliant JSON document.
    """
    eps = extract_entrypoints(repo_root)
    return {
        "kind": "lenskit.entrypoints",
        "version": "1.0",
        "run_id": run_id,
        "canonical_dump_index_sha256": canonical_sha256,
        "entrypoints": eps
    }
