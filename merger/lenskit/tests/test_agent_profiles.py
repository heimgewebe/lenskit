import pytest
from merger.lenskit.retrieval.output_projection import project_output

def test_agent_profile_lookup_minimal():
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

    projected = project_output(mock_result, output_profile="lookup_minimal")
    hits = projected.get("hits", [])
    assert len(hits) == 2

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

    projected = project_output(mock_result, output_profile="review_context")
    hits = projected.get("hits", [])
    assert len(hits) == 2

    for hit in hits:
        assert "explain" in hit
        assert "graph_context" not in hit

    assert "surrounding_context" in hits[0]
    assert "surrounding_context" not in hits[1]
