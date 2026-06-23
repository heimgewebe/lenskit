import pytest
from merger.lenskit.core.pr_delta_cards import produce_pr_delta_card, produce_pr_delta_cards

def test_produce_pr_delta_card_added():
    delta_context = {"repo": "myrepo", "generated_at": "2023-01-01T00:00:00Z"}
    file_entry = {"path": "src/main.py", "status": "added"}
    card = produce_pr_delta_card(delta_context, file_entry)
    assert card["kind"] == "repolens.pr_delta_card"
    assert card["delta_context"]["repo"] == "myrepo"
    assert card["path"] == "src/main.py"
    assert card["change_status"] == "added"
    assert "truth" in card["does_not_establish"]

def test_produce_pr_delta_card_invalid_status():
    delta_context = {"repo": "myrepo", "generated_at": "2023-01-01T00:00:00Z"}
    file_entry = {"path": "src/main.py", "status": "modified"}
    with pytest.raises(ValueError, match="Invalid change_status"):
        produce_pr_delta_card(delta_context, file_entry)

def test_produce_pr_delta_cards_batch_success():
    delta = {
        "repo": "myrepo",
        "generated_at": "2023-01-01T00:00:00Z",
        "summary": {"added": 1, "changed": 1, "removed": 1},
        "files": [
            {"path": "src/removed.py", "status": "removed"},
            {"path": "src/added.py", "status": "added"},
            {"path": "src/changed.py", "status": "changed"},
        ]
    }
    source_provenance = {"source_delta_sha256": "0" * 64}
    cards = produce_pr_delta_cards(delta, source_provenance=source_provenance)
    
    assert len(cards) == 3
    # Sorted by path
    assert cards[0]["path"] == "src/added.py"
    assert cards[1]["path"] == "src/changed.py"
    assert cards[2]["path"] == "src/removed.py"

    assert cards[0]["source_provenance"]["source_delta_sha256"] == "0" * 64

def test_produce_pr_delta_cards_empty():
    delta = {
        "repo": "myrepo",
        "generated_at": "2023-01-01T00:00:00Z",
        "summary": {"added": 0, "changed": 0, "removed": 0},
        "files": []
    }
    cards = produce_pr_delta_cards(delta)
    assert cards == []

def test_produce_pr_delta_cards_summary_mismatch():
    delta = {
        "repo": "myrepo",
        "generated_at": "2023-01-01T00:00:00Z",
        "summary": {"added": 0, "changed": 0, "removed": 0},
        "files": [{"path": "src/added.py", "status": "added"}]
    }
    with pytest.raises(ValueError, match="Source summary counts do not match"):
        produce_pr_delta_cards(delta)

def test_produce_pr_delta_cards_duplicate_paths():
    delta = {
        "repo": "myrepo",
        "generated_at": "2023-01-01T00:00:00Z",
        "summary": {"added": 2, "changed": 0, "removed": 0},
        "files": [
            {"path": "src/added.py", "status": "added"},
            {"path": "src/added.py", "status": "added"}
        ]
    }
    with pytest.raises(ValueError, match="Duplicate path in delta"):
        produce_pr_delta_cards(delta)

def test_produce_pr_delta_cards_deterministic():
    delta = {
        "repo": "myrepo",
        "generated_at": "2023-01-01T00:00:00Z",
        "summary": {"added": 1, "changed": 1, "removed": 0},
        "files": [
            {"path": "src/b.py", "status": "added"},
            {"path": "src/a.py", "status": "changed"},
        ]
    }
    cards = produce_pr_delta_cards(delta)
    assert cards[0]["path"] == "src/a.py"
    assert cards[1]["path"] == "src/b.py"
