import re
from typing import Dict, Any, List

STOP_VERBS = {
    "show", "find", "get", "where", "how", "what", "is", "are", "does", "do",
    "search", "list", "display", "locate", "explain", "give", "me"
}

INTENT_TRIGGERS = {
    "entrypoint": {"entrypoint", "start", "main", "cli", "cmd", "run", "execute", "entry", "boot"},
    "architecture": {"architecture", "structure", "design", "layer", "module", "component", "dependency"},
    "security": {"security", "auth", "token", "credential", "password", "secret", "vulnerability", "leak"},
    "test": {"test", "mock", "fixture", "assert", "spec", "verify", "suite"}
}

SYNONYMS = {
    "index": ["indexing", "build_index", "indexer"],
    "indexing": ["index", "build_index", "indexer"],
    "config": ["configuration", "settings", "options"],
    "configuration": ["config", "settings", "options"],
    "settings": ["config", "configuration", "options"],
    "db": ["database", "sqlite", "sql"],
    "database": ["db", "sqlite", "sql"],
    "error": ["exception", "fail", "failure", "crash"],
    "exception": ["error", "fail", "failure", "crash"],
    "auth": ["authentication", "login", "credentials", "security"],
    "authentication": ["auth", "login", "credentials", "security"]
}

def route_query(query_text: str, overmatch_guard: bool = False) -> Dict[str, Any]:
    """
    Parses the query text and extracts intents, removes stop-verbs,
    and performs synonym OR-expansion if overmatch_guard is False.
    """
    if not query_text:
        return {
            "intent": "unknown",
            "fts_query": "",
            "synonyms_used": []
        }

    # Normalize query
    tokens = re.findall(r'\b\w+\b', query_text.lower())

    # 1. Intent Extraction
    detected_intent = "unknown"
    for intent, triggers in INTENT_TRIGGERS.items():
        if any(t in tokens for t in triggers):
            detected_intent = intent
            break

    # 2. Stop-Verb Removal
    filtered_tokens = [t for t in tokens if t not in STOP_VERBS]
    if not filtered_tokens:
        # If query was entirely stop-verbs, fallback to original tokens
        filtered_tokens = tokens

    # 3. Synonym OR-Expansion
    fts_parts = []
    synonyms_used = set()

    for token in filtered_tokens:
        if not overmatch_guard and token in SYNONYMS:
            expansions = [token] + SYNONYMS[token]
            synonyms_used.update(SYNONYMS[token])
            # Construct OR group, e.g., (index OR indexing OR build_index)
            or_group = " OR ".join(expansions)
            fts_parts.append(f"({or_group})")
        else:
            fts_parts.append(token)

    # Join the FTS parts
    fts_query = " AND ".join(fts_parts)

    return {
        "intent": detected_intent,
        "fts_query": fts_query,
        "synonyms_used": sorted(list(synonyms_used))
    }
