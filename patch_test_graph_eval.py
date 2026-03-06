import re

with open("merger/lenskit/tests/test_graph_eval.py", "r") as f:
    code = f.read()

bad = r"""    ret = cmd_eval\.run_eval\(args\)
    # The eval loop intercepts RuntimeError internally and puts it in the details block\. It only returns 0 if all runs complete but some have failures\. Let's check the JSON output\.
    assert ret == 0
    captured = capsys\.readouterr\(\)
    detail = json\.loads\(captured\.out\)\["details"\]\[0\]
    assert "Invalid graph index JSON" in detail\["error"\]"""

good = """    ret = cmd_eval.run_eval(args)
    assert ret == 1
    captured = capsys.readouterr()
    assert "Invalid graph index JSON" in captured.err"""

code = re.sub(bad, good, code)

with open("merger/lenskit/tests/test_graph_eval.py", "w") as f:
    f.write(code)
