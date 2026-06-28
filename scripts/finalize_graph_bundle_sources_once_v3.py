from pathlib import Path


path = Path("scripts/finalize_graph_bundle_sources_once.py")
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
indexes = []
for index, line in enumerate(lines):
    if "if __name__ == '__main__'" in line and "\\n" in line:
        indexes.append(index)
if len(indexes) != 1:
    raise RuntimeError(f"expected one fixture line, found {len(indexes)}")
index = indexes[0]
lines[index] = lines[index].replace("\\n", "\\\\n")
path.write_text("".join(lines), encoding="utf-8")

import finalize_graph_bundle_sources_once_v2  # noqa: E402,F401
