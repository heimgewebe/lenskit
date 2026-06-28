from pathlib import Path


path = Path("merger/lenskit/retrieval/query_core.py")
text = path.read_text(encoding="utf-8")
old = "            graph_root = index_path.resolve().parent\n"
new = "            graph_root = index_path.parent\n"
count = text.count(old)
if count != 1:
    raise SystemExit(f"expected one graph-root resolution, found {count}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
