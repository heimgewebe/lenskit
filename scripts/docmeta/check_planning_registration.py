import json
import os
import re
import sys
import glob

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_PATH_REF_RE = re.compile(r"(?:docs|scripts)/[A-Za-z0-9_./-]+")

# doc_type values that make a spec a planning artifact
_PLANNING_DOC_TYPES = {"roadmap", "plan", "status", "status-matrix"}

# Terminal status values that are excluded from checks
_TERMINAL_STATUSES = {"deprecated", "superseded", "archived", "deferred"}

# Explicit scan patterns: (glob_pattern, extra_filter_fn_or_None)
# extra_filter_fn receives (rel_path, meta) and returns True if the file should be checked
_SCAN_PATTERNS = [
    ("docs/blueprints/*.md", None),
    ("docs/roadmap/*.md", None),
    ("docs/roadmap.md", None),
    ("docs/reports/*status*.md", None),
    ("docs/reports/*roadmap*.md", None),
    ("docs/reports/*next-step*.md", None),
    ("docs/specs/*.md", "_is_planning_spec"),
]

# Directories to exclude from scanning (relative to REPO_ROOT)
_EXCLUDED_PREFIXES = (
    "docs/_generated/",
    "docs/proofs/",
    "docs/runbooks/",
    "docs/reference/",
    "docs/adr/",
    "docs/policies/",
    "docs/process/",
    "docs/claims/",
)


def _normalize_ref(raw):
    """Normalize a path-like reference extracted from markdown/free text."""
    ref = str(raw).strip().strip("`'\"")
    ref = ref.rstrip(".,);:]")
    ref = ref.strip().strip("`'\"")
    return ref


def _extract_path_refs(text):
    """Extract normalized docs/ and scripts/ references from free text."""
    refs = set()
    if not text:
        return refs
    for match in _PATH_REF_RE.findall(text):
        ref = _normalize_ref(match)
        if ref:
            refs.add(ref)
    return refs


def _read_text(rel_path):
    full_path = os.path.join(REPO_ROOT, rel_path)
    if not os.path.exists(full_path):
        return "", f"File not found: {rel_path}"
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read(), None


def get_registered_paths():
    registered = set()
    findings = []

    # 1. docs/tasks/index.json
    index_text, err = _read_text("docs/tasks/index.json")
    if err:
        findings.append({
            "code": "CONTROL_FILE_MISSING",
            "path": "docs/tasks/index.json",
            "reason": err,
            "suggestion": "Create docs/tasks/index.json with a tasks array.",
            "source": "planning-registration",
        })
    else:
        try:
            data = json.loads(index_text)
            for task in data.get("tasks", []):
                for path in task.get("evidence", []) or []:
                    ref = _normalize_ref(path)
                    if ref:
                        registered.add(ref)
                for item in task.get("missing_evidence", []) or []:
                    registered.update(_extract_path_refs(str(item)))
        except json.JSONDecodeError as e:
            findings.append({
                "code": "CONTROL_FILE_PARSE_ERROR",
                "path": "docs/tasks/index.json",
                "reason": f"Invalid JSON: {e}",
                "suggestion": "Fix the JSON syntax in docs/tasks/index.json.",
                "source": "planning-registration",
            })

    # 2. docs/tasks/board.md
    board_text, err = _read_text("docs/tasks/board.md")
    if err:
        findings.append({
            "code": "CONTROL_FILE_MISSING",
            "path": "docs/tasks/board.md",
            "reason": err,
            "suggestion": "Create docs/tasks/board.md as the task board.",
            "source": "planning-registration",
        })
    else:
        registered.update(_extract_path_refs(board_text))

    # 3. docs/roadmap.md
    roadmap_text, err = _read_text("docs/roadmap.md")
    if err:
        findings.append({
            "code": "CONTROL_FILE_MISSING",
            "path": "docs/roadmap.md",
            "reason": err,
            "suggestion": "Create docs/roadmap.md as the project roadmap.",
            "source": "planning-registration",
        })
    else:
        for match in re.findall(r'\]\(([^)]+)\)', roadmap_text):
            match = _normalize_ref(match)
            if match.endswith('.md'):
                if not match.startswith('docs/'):
                    registered.add(os.path.normpath(os.path.join('docs', match)))
                else:
                    registered.add(match)
        registered.update(_extract_path_refs(roadmap_text))

    # Self-register control files
    registered.add("docs/tasks/index.json")
    registered.add("docs/tasks/board.md")
    registered.add("docs/roadmap.md")

    return registered, findings


def _is_excluded(rel_path):
    for prefix in _EXCLUDED_PREFIXES:
        if rel_path.startswith(prefix):
            return True
    return False


def _is_planning_spec(rel_path, meta):
    """Return True if a docs/specs file counts as a planning artifact."""
    doc_type = meta.get("doc_type", "").strip().strip('"\'')
    return doc_type in _PLANNING_DOC_TYPES


def is_registered(rel_path, registered_paths):
    if rel_path in registered_paths:
        return True
    for rp in registered_paths:
        if rp.endswith("/") and rel_path.startswith(rp):
            return True
    return False


def parse_markdown_meta(filepath):
    meta = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if lines and lines[0].strip() == "---":
                for i in range(1, len(lines)):
                    if lines[i].strip() == "---":
                        break
                    if ":" in lines[i]:
                        parts = lines[i].split(":", 1)
                        key = parts[0].strip()
                        val = parts[1].strip().strip('"\'')
                        if val.startswith("[") and val.endswith("]"):
                            meta[key] = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
                        else:
                            meta[key] = val
    except OSError as exc:
        print(f"Warning: failed to read {filepath}: {exc}", file=sys.stderr)
    except UnicodeDecodeError as exc:
        print(f"Warning: failed to decode {filepath}: {exc}", file=sys.stderr)
    except Exception as exc:
        print(f"Warning: unexpected error parsing {filepath}: {exc}", file=sys.stderr)
    return meta


def _collect_scan_targets():
    """Collect (rel_path, extra_filter_name) tuples to scan."""
    targets = []
    for pattern, extra_filter in _SCAN_PATTERNS:
        full_pattern = os.path.join(REPO_ROOT, pattern)
        for full_path in glob.glob(full_pattern):
            rel_path = os.path.relpath(full_path, REPO_ROOT)
            if not _is_excluded(rel_path):
                targets.append((rel_path, extra_filter))
    return targets


def run_checks():
    registered_paths, findings = get_registered_paths()

    for rel_path, extra_filter_name in _collect_scan_targets():
        full_path = os.path.join(REPO_ROOT, rel_path)
        if not os.path.isfile(full_path):
            continue

        meta = parse_markdown_meta(full_path)

        # Skip terminal-status artifacts
        status = meta.get("status", "").strip().strip('"\'')
        if status in _TERMINAL_STATUSES:
            continue

        # Apply extra filter for specs
        if extra_filter_name == "_is_planning_spec":
            if not _is_planning_spec(rel_path, meta):
                continue

        if not is_registered(rel_path, registered_paths):
            findings.append({
                "code": "UNREGISTERED_PLANNING_ARTIFACT",
                "path": rel_path,
                "reason": "Planning artifact is active but not registered in task-control or roadmap.",
                "suggestion": "Add the path to docs/tasks/index.json evidence, docs/tasks/board.md, or docs/roadmap.md.",
                "source": "planning-registration",
            })

    return findings


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Check registration of planning artifacts.")
    parser.add_argument("--strict", action="store_true", help="Fail if unregistered artifacts are found.")
    args = parser.parse_args(argv)

    findings = run_checks()
    if not findings:
        print("All planning artifacts are registered.")
        return 0

    print("Findings:")
    for f in findings:
        print(f"  {f['code']} in {f['path']}: {f['reason']}")
        print(f"    Suggestion: {f['suggestion']}")

    if args.strict:
        return 1
    print("Report-only mode: findings do not fail CI. Use --strict to fail.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
