import re

with open("merger/lenskit/tests/test_retrieval_eval.py", "r") as f:
    code = f.read()

bad = r"""    def mock_execute\(\*args, \*\*kwargs\):
        raise RuntimeError\("Mock DB Crash"\)
    monkeypatch\.setattr\(eval_core, "execute_query", mock_execute\)

    cmd_eval\.run_eval\(Args\(\)\)
    captured = capsys\.readouterr\(\)
    detail = json\.loads\(captured\.out\)\["details"\]\[0\]
    # The output from the test failure format puts "error: Mock DB Crash" in `hit_path`
    # Let's adjust to check the actual returned structure cleanly\.
    assert "Mock DB Crash" in detail\["hit_path"\]"""

good = """    def mock_execute(*args, **kwargs):
        raise RuntimeError("Mock DB Crash")
    monkeypatch.setattr(eval_core, "execute_query", mock_execute)

    cmd_eval.run_eval(Args())
    captured = capsys.readouterr()
    detail = json.loads(captured.out)["details"][0]
    assert detail["error"] == "Mock DB Crash\""""

# Wait, we already patched it back correctly in main previously, maybe I just need to verify the test file.
