import re

with open("merger/lenskit/architecture/graph_index.py", "r") as f:
    code = f.read()

bad = r"""    for node_id in adjacency\.keys\(\):
        index\["distances"\]\[node_id\] = distances\.get\(node_id, -1\)"""

good = """    for node_id in adjacency.keys():
        dist = distances.get(node_id, -1)
        index["distances"][node_id] = dist
        # If node_id is something like "file:src/main.py", we are already fine.
        # But if the node has a path, and it's not strictly 'file:<path>',
        # let's inject a guaranteed 'file:<path>' mapping to bridge the consumer.
        path = None
        for n in graph.get("nodes", []):
            if n["node_id"] == node_id:
                path = n.get("path")
                break

        if path:
            file_key = f"file:{path}"
            if file_key != node_id:
                index["distances"][file_key] = dist"""

code = re.sub(bad, good, code)

with open("merger/lenskit/architecture/graph_index.py", "w") as f:
    f.write(code)
