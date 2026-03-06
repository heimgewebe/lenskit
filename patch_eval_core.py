import re

with open("merger/lenskit/retrieval/eval_core.py", "r") as f:
    code = f.read()

# I forgot to actually pass the graph arguments into execute_query in the previous fix!
eq_old = """            res = execute_query(
                index_path=index_path,
                query_text=q_text,
                k=k,
                filters=filters,
                embedding_policy=embedding_policy,
                explain=True
            )"""

eq_new = """            res = execute_query(
                index_path=index_path,
                query_text=q_text,
                k=k,
                filters=filters,
                embedding_policy=embedding_policy,
                explain=True,
                graph_index_path=graph_index_path,
                graph_weights=graph_weights
            )"""

code = code.replace(eq_old, eq_new)

with open("merger/lenskit/retrieval/eval_core.py", "w") as f:
    f.write(code)
