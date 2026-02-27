# Retrieval Gold Queries

Die folgenden 15 "Gold Queries" definieren die Zielwerte (Benchmarks) für das lenskit Retrieval-System.
Ein Retrieval-System gilt als erfolgreich, wenn es für diese Queries relevante Ergebnisse (Chunks) in den Top-10 liefert.

## Benchmark-Zielwerte (Eval Runner pending)
- **TTR (Time-to-Relevant):** < 2 Sekunden für CLI-Output.
- **Recall@10:** Mindestens 1 relevantes Ergebnis in den Top-10.
- **Explainability:** Mindestens Engine + Filter + Query-Mode (Token-Matches optional).

## Query Liste

1.  **"find auth logic"**
    *   *Intent:* Suche nach Authentifizierungs-Code oder Konfiguration.
    *   *Expected:* `auth.py`, `middleware`, `login` handlers, `security` config.
    *   *Filter:* `layer=core` (optional)

2.  **"find rate limiting"**
    *   *Intent:* Suche nach Drosselungs-Logik.
    *   *Expected:* `ratelimit`, `throttling`, decorators, middleware.

3.  **"find database schema"**
    *   *Intent:* Suche nach Tabellendefinitionen oder Migrations.
    *   *Expected:* `models.py`, `schema.sql`, `migrations/`.
    *   *Filter:* `ext=sql` oder `ext=py`

4.  **"find error handling"**
    *   *Intent:* Suche nach Exception-Klassen oder globalen Error-Handlern.
    *   *Expected:* `exceptions.py`, `error_handler`, `try/except` blocks in main loops.

5.  **"find api routes"**
    *   *Intent:* Suche nach REST-Endpunkten.
    *   *Expected:* `routes.py`, `urls.py`, `@app.get`, `@app.post`.

6.  **"find docker configuration"**
    *   *Intent:* Suche nach Container-Setup.
    *   *Expected:* `Dockerfile`, `docker-compose.yml`.
    *   *Filter:* `path=docker`

7.  **"find logging setup"**
    *   *Intent:* Suche nach Logger-Initialisierung.
    *   *Expected:* `logging.config`, `logger =`, `structlog`.

8.  **"find cli entrypoints"**
    *   *Intent:* Suche nach CLI-Commands.
    *   *Expected:* `argparse`, `click`, `if __name__ == "__main__"`.
    *   *Filter:* `layer=cli`

9.  **"find secrets handling"**
    *   *Intent:* Suche nach Code, der Secrets lädt oder maskiert.
    *   *Expected:* `os.environ`, `.env` loading, `redact`, `mask`.

10. **"find test fixtures"**
    *   *Intent:* Suche nach Test-Daten oder Setup-Code.
    *   *Expected:* `conftest.py`, `fixtures/`, `@pytest.fixture`.
    *   *Filter:* `layer=test`

11. **"find user model"**
    *   *Intent:* Suche nach der Definition des Users.
    *   *Expected:* `class User`, `type User`.

12. **"find config parsing"**
    *   *Intent:* Suche nach Logik, die Konfigurationen liest.
    *   *Expected:* `config.py`, `settings.py`, `yaml.safe_load`.

13. **"find dependency definition"**
    *   *Intent:* Suche nach externen Abhängigkeiten.
    *   *Expected:* `requirements.txt`, `pyproject.toml`, `package.json`.

14. **"find middleware"**
    *   *Intent:* Suche nach HTTP-Middleware.
    *   *Expected:* `middleware/`, `process_request`, `process_response`.

15. **"find index generation"**
    *   *Intent:* (Self-Reflexive) Suche nach dem Code, der den Index baut.
    *   *Expected:* `index_db.py`, `build_index`.
