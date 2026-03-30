from merger.lenskit.retrieval.output_projection import project_output

def test_agent_profile_lookup_minimal():
    # Mock result mimicking what execute_query returns
    mock_result = {
        "context_bundle": {
            "hits": [
                {
                    "id": "1",
                    "explain": {"bm25": 1.0},
                    "graph_context": {"distance": 1},
                    "surrounding_context": "def foo():\n    pass\n"
                },
                {
                    "id": "2",
                    "explain": {"bm25": 0.5},
                    "graph_context": {"distance": 2},
                    "surrounding_context": None
                }
            ]
        },
        "query_trace": {"status": "ok"} # Adding query_trace to verify the wrapper contract
    }

    projected = project_output(mock_result, output_profile="lookup_minimal")

    # Contract says if query_trace is present, it returns {"context_bundle": ..., "query_trace": ...}
    assert "context_bundle" in projected
    assert "query_trace" in projected

    hits = projected["context_bundle"].get("hits", [])
    assert len(hits) == 2

    # lookup_minimal should strip explain, graph_context, and surrounding_context
    for hit in hits:
        assert "explain" not in hit
        assert "graph_context" not in hit
        assert "surrounding_context" not in hit

def test_agent_profile_review_context():
    mock_result = {
        "context_bundle": {
            "hits": [
                {
                    "id": "1",
                    "explain": {"bm25": 1.0},
                    "graph_context": {"distance": 1},
                    "surrounding_context": "def foo():\n    pass\n"
                },
                {
                    "id": "2",
                    "explain": {"bm25": 0.5},
                    "graph_context": {"distance": 2},
                    "surrounding_context": None
                }
            ]
        }
    }

    # Here query_trace is missing, so it should return the bundle directly
    projected = project_output(mock_result, output_profile="review_context")
    hits = projected.get("hits", [])
    assert len(hits) == 2

    # review_context should strip graph_context, but keep explain and surrounding_context (if not None)
    for hit in hits:
        assert "explain" in hit
        assert "graph_context" not in hit

    assert "surrounding_context" in hits[0]
    # For hit 2, surrounding_context was None, so it is stripped
    assert "surrounding_context" not in hits[1]

def test_agent_profile_lookup_minimal_without_trace():
    # Mock result without query_trace
    mock_result = {
        "context_bundle": {
            "hits": [
                {
                    "id": "1",
                    "explain": {"bm25": 1.0},
                    "graph_context": {"distance": 1},
                    "surrounding_context": "def foo():\n    pass\n"
                },
                {
                    "id": "2",
                    "explain": {"bm25": 0.5},
                    "graph_context": {"distance": 2},
                    "surrounding_context": None
                }
            ]
        }
    }

    # Contract says if query_trace is absent, it returns the bundle directly
    projected = project_output(mock_result, output_profile="lookup_minimal")

    hits = projected.get("hits", [])
    assert len(hits) == 2

    # lookup_minimal should strip explain, graph_context, and surrounding_context
    for hit in hits:
        assert "explain" not in hit
        assert "graph_context" not in hit
        assert "surrounding_context" not in hit

def test_agent_profile_review_context_with_trace():
    mock_result = {
        "context_bundle": {
            "hits": [
                {
                    "id": "1",
                    "explain": {"bm25": 1.0},
                    "graph_context": {"distance": 1},
                    "surrounding_context": "def foo():\n    pass\n"
                },
                {
                    "id": "2",
                    "explain": {"bm25": 0.5},
                    "graph_context": {"distance": 2},
                    "surrounding_context": None
                }
            ]
        },
        "query_trace": {"status": "ok"} # Adding query_trace
    }

    # Contract says if query_trace is present, it returns a wrapper
    projected = project_output(mock_result, output_profile="review_context")

    assert "context_bundle" in projected
    assert "query_trace" in projected

    hits = projected["context_bundle"].get("hits", [])
    assert len(hits) == 2

    # review_context should strip graph_context, but keep explain and surrounding_context (if not None)
    for hit in hits:
        assert "explain" in hit
        assert "graph_context" not in hit

    assert "surrounding_context" in hits[0]
    assert "surrounding_context" not in hits[1]

def test_agent_federated_conflict_warning():
    mock_result = {
        "context_bundle": {
            "hits": [
                {
                    "id": "1",
                    "explain": {"bm25": 1.0},
                    "graph_context": {"distance": 1},
                    "surrounding_context": "def foo():\n    pass\n"
                }
            ]
        },
        "federation_conflicts": [
            {
                "conflict_id": "conflict_0",
                "type": "path",
                "description": "Conflict description",
                "resolution": "unresolved",
                "involved_results": ["1"]
            }
        ],
        "warnings": ["Low evidence density"]
    }

    # Contract says if federation_conflicts or warnings are present, it returns a wrapper
    projected = project_output(mock_result, output_profile="agent_minimal")

    assert "context_bundle" in projected
    assert "federation_conflicts" in projected
    assert projected["federation_conflicts"][0]["conflict_id"] == "conflict_0"

    assert "warnings" in projected
    assert len(projected["warnings"]) == 1

    hits = projected["context_bundle"].get("hits", [])
    assert len(hits) == 1

    # agent_minimal should strip explain, graph_context
    for hit in hits:
        assert "explain" not in hit
        assert "graph_context" not in hit

def test_agent_federated_conflict_empty_no_wrapper():
    mock_result = {
        "context_bundle": {
            "hits": [
                {
                    "id": "1"
                }
            ]
        },
        "federation_conflicts": [],
        "warnings": []
    }

    # If lists are empty, they should NOT trigger a wrapper, returning the bundle directly
    projected = project_output(mock_result, output_profile="agent_minimal")

    assert "context_bundle" not in projected
    assert "federation_conflicts" not in projected
    assert "warnings" not in projected
    assert "hits" in projected
