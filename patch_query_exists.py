import re

with open("merger/lenskit/retrieval/query_core.py", "r") as f:
    code = f.read()

bad = r"""        if graph_index_path and graph_index_path\.exists\(\):
            try:
                with graph_index_path\.open\(\) as f:
                    graph_index = json\.load\(f\)
            except Exception as e:
                raise RuntimeError\(f"Invalid graph index JSON at \{graph_index_path\}: \{e\}"\) from e"""

good = """        if graph_index_path:
            if not graph_index_path.exists():
                raise RuntimeError(f"Explicitly provided graph index file does not exist: {graph_index_path}")
            try:
                with graph_index_path.open() as f:
                    graph_index = json.load(f)
            except Exception as e:
                raise RuntimeError(f"Invalid graph index JSON at {graph_index_path}: {e}") from e"""

code = re.sub(bad, good, code)

with open("merger/lenskit/retrieval/query_core.py", "w") as f:
    f.write(code)
