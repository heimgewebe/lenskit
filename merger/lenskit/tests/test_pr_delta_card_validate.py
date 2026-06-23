from merger.lenskit.core.pr_delta_cards import produce_pr_delta_card
from merger.lenskit.core.pr_delta_card_validate import validate_pr_delta_card

def _valid_card():
    delta_context = {"repo": "myrepo", "generated_at": "2023-01-01T00:00:00Z"}
    file_entry = {"path": "src/main.py", "status": "added"}
    return produce_pr_delta_card(delta_context, file_entry)

def test_validate_pr_delta_card_success():
    card = _valid_card()
    result = validate_pr_delta_card(card)
    assert result["status"] == "pass"

def test_validate_pr_delta_card_invalid_schema():
    card = _valid_card()
    card["extra_field"] = "not_allowed"
    result = validate_pr_delta_card(card)
    assert result["status"] == "fail"
    assert any(c["name"] == "schema_validation" and c["status"] == "fail" for c in result["checks"])

def test_validate_pr_delta_card_wrong_status():
    card = _valid_card()
    card["change_status"] = "unknown"
    result = validate_pr_delta_card(card)
    assert result["status"] == "fail"
    assert any(c["name"] == "schema_validation" and c["status"] == "fail" for c in result["checks"])

def test_validate_pr_delta_card_wrong_lens_projection():
    card = _valid_card()
    card["primary_lens"] = "invalid_lens"
    result = validate_pr_delta_card(card)
    assert result["status"] == "fail"
    assert any(c["name"] == "producer_coherence" and c["status"] == "fail" for c in result["checks"])

def test_validate_pr_delta_card_wrong_path_coherence():
    card = _valid_card()
    # Change path without updating lens projection
    card["path"] = "src/other.py"
    result = validate_pr_delta_card(card)
    assert result["status"] == "fail"
    assert any(c["name"] == "producer_coherence" and c["status"] == "fail" for c in result["checks"])

def test_validate_pr_delta_card_missing_negative_semantics():
    card = _valid_card()
    card["does_not_establish"].pop()
    result = validate_pr_delta_card(card)
    assert result["status"] == "fail"
    assert any(c["name"] == "schema_validation" and c["status"] == "fail" for c in result["checks"])
