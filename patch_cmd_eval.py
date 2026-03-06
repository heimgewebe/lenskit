import re

with open("merger/lenskit/cli/cmd_eval.py", "r") as f:
    code = f.read()

bad = r"""    out = do_eval\(
        index_path,
        queries_path,
        args\.k,
        is_json_mode,
        is_stale,
        policy_instance,
        graph_index_path=Path\(args\.graph_index\) if getattr\(args, "graph_index", None\) else None,
        graph_weights=graph_weights_dict
    \)
    if out is None:
        return 1"""

good = """    try:
        out = do_eval(
            index_path,
            queries_path,
            args.k,
            is_json_mode,
            is_stale,
            policy_instance,
            graph_index_path=Path(args.graph_index) if getattr(args, "graph_index", None) else None,
            graph_weights=graph_weights_dict
        )
    except RuntimeError as e:
        print(f"Error during eval: {e}", file=sys.stderr)
        return 1

    if out is None:
        return 1"""

code = re.sub(bad, good, code)

with open("merger/lenskit/cli/cmd_eval.py", "w") as f:
    f.write(code)
