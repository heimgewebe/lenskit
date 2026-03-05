from merger.lenskit.retrieval.router import route_query

def test_route_query_empty():
    res = route_query("")
    assert res["intent"] == "unknown"
    assert res["fts_query"] == ""
    assert res["synonyms_used"] == []

def test_route_query_stop_verbs_removal():
    res = route_query("show me where the index is")
    assert res["intent"] == "unknown"
    # "show", "me", "where", "is" are stop verbs
    # remaining: "the", "index"
    # "index" is expanded
    assert "the" in res["fts_query"]
    assert "(index OR indexing OR build_index OR indexer)" in res["fts_query"]

def test_route_query_all_stop_verbs():
    res = route_query("show me where is")
    assert res["intent"] == "unknown"
    # fallback to original tokens
    assert "show AND me AND where AND is" == res["fts_query"]

def test_route_query_intent_extraction():
    res = route_query("find cli configuration")
    assert res["intent"] == "entrypoint" # "cli" triggers entrypoint
    assert "cli" in res["fts_query"]

    res2 = route_query("show me the auth layer")
    # "auth" (security) comes before "layer" (architecture)
    assert res2["intent"] == "security"

    res3 = route_query("what is the architecture of the auth service")
    # "architecture" comes before "auth"
    assert res3["intent"] == "architecture"

def test_route_query_fts_escaping():
    # 'and' and 'or' are reserved in FTS5
    res = route_query("find auth or config")
    # 'find' is stop verb
    # 'auth' -> expanded
    # 'or' -> should be "or"
    # 'config' -> expanded
    assert '"or"' in res["fts_query"]
    assert " OR " in res["fts_query"] # The synonym separator OR should still exist, but not quoted

    # check that we indeed have the exact phrase for token "or" escaped
    # Should look roughly like: (auth OR authentication...) AND "or" AND (config OR ...)
    assert 'AND "or" AND' in res["fts_query"]

def test_route_query_synonym_expansion():
    res = route_query("database settings")
    assert "(database OR db OR sqlite OR sql)" in res["fts_query"]
    assert "(settings OR config OR configuration OR options)" in res["fts_query"]
    assert "db" in res["synonyms_used"]
    assert "sqlite" in res["synonyms_used"]

def test_route_query_overmatch_guard():
    res = route_query("database settings", overmatch_guard=True)
    assert res["fts_query"] == "database AND settings"
    assert res["synonyms_used"] == []
