# Lenskit Output- und Repo-Härtung v1 (Abhakbare Blaupause)

## These / Antithese / Synthese

### These
- [x] Lenskit besitzt eine tragfähige Artefaktordnung (canonical Markdown, Chunk-Index, Dump-Index, SQLite-Cache, Manifest, Architektur-Summary).
- [x] Rollen sind im Manifest getrennt:
  - [x] `canonical_md` = Inhaltsquelle.
  - [x] `chunk_index_jsonl` = Retrieval-Index.
  - [x] `sqlite_index` = Runtime-Cache.

### Antithese
- [x] Output ist vollständig, aber für Agenten noch nicht zuverlässig genug suchbar, zitierbar und health-geprüft.
- [x] Lokalbefund:
  - [x] `chunk_index.jsonl`: 539 Chunks.
  - [x] `content_range_ref` bei 539/539.
  - [x] `content` bei 0/539.
  - [x] SQLite: 539 FTS-Zeilen, `avg(length(content)) = 0.0`.
- [x] Kurzbild: sauberer Katalog, leere Bücher.

### Synthese
- [ ] Fokus nicht auf „größerem Dump", sondern auf **Evidence-Control-Plane**.
- [ ] Jeder Output muss sich selbst beweisen können: vollständig, suchbar, auflösbar, zitierbar, hash-konsistent, agententauglich.
- [ ] Leitfrage: Wie erzeugt Lenskit Outputs, die Agenten nicht mehr falsch lesen können?

---

## Präzisierungen vor Umsetzung

- Lokal geprüfte Befunde sind Momentaufnahmen des Outputs `lenskit-max-260502-1126_*`; sie gelten nicht automatisch für spätere Outputs.
- Jeder Lokalbefund muss vor Codeänderung durch ein reproduzierbares Diagnose-Skript oder einen Test bestätigt werden.
- Hash-Prüfung erfolgt über den originalen Byte-Slice aus `canonical_md`, nicht über dekodierten oder normalisierten Text.
- Noch nicht existierende CLI-Kommandos werden ausdrücklich als „geplant" markiert.
- `output_health.json` prüft zunächst Range-Ref v1; Range-Ref v2 erweitert später die Zeilenachsen.
- `agent_pack_present` ist bis Abschluss von Arbeitspaket D nur warnend, danach blockierend.
- `derived_index.json` bleibt Registry für abgeleitete Artefakte; `output_health.json` bleibt funktionaler Health-Report.

---

## 0) Zielbild

- [ ] Pipeline als prüfbare Kette etablieren:
  - [ ] `canonical_md` = vollständige Wahrheit.
  - [ ] `chunk_index_jsonl` = präzise Range-Navigation.
  - [ ] `sqlite_index` = echte Volltextsuche.
  - [ ] `agent_reading_pack` = kompakter Einstieg.
  - [ ] `output_health.json` = Selbstprüfung.
  - [ ] Query/Context APIs = zitierbar, begrenzt, claim-bewusst.

---

## 1) Belegter Ist-Zustand

- [x] Dump vollständig: 357/357 Textdateien.
- [x] `merge.md` als kanonische Quelle markiert.
- [x] Reading Policy: Markdown kanonisch, JSON Navigation/Metadaten.
- [x] Rollenmodell trennt Autoritäten (`canonical_content`, `navigation_index`, `retrieval_index`, `runtime_cache`, `diagnostic_signal`).
- [x] `range-ref.v1`: Byte-/Line-Range + `content_sha256`.
- [x] Query-Result-Schema kennt `claim_boundaries`, `evidence_basis`, `requires_live_check`.
- [x] Lokal geprüft: Chunk-Index ohne Inline-Content, SQLite-FTS ohne Content.
- [ ] `derived_index.json` bleibt Registry für abgeleitete Artefakte; `output_health.json` wird separates funktionales Prüfartefakt. `derived_index.json` kann auf `output_health.json` verweisen.

---

## 2) Leitentscheidung (Priorität)

- [ ] **P1:** SQLite-FTS mit echtem Inhalt füllen.
- [ ] **P2:** Range-Refs semantisch entwirren.
- [ ] **P3:** Output-Health erzwingen.
- [ ] **P4:** Agent Reading Pack erzeugen.
- [ ] **P5:** Redaction/Profile trennen.
- [ ] **P6:** Architektur-Summary vertiefen.

---

## Arbeitspaket A — FTS aus Range-Refs rekonstruieren (Optimierungsgrad 0.88)

### Problem
- [x] Chunk-Index hat keinen Inline-`content`.
- [x] SQLite-Builder darf nicht blind `chunk["content"]` erwarten.

### Ziel
- [ ] `sqlite_index` liefert echte Volltextsuche, auch ohne Inline-Content im Chunk-Index.

### Umsetzung
- [ ] Dateien bearbeiten:
  - [ ] `merger/lenskit/retrieval/index_db.py`
  - [ ] `merger/lenskit/core/range_resolver.py`
  - [ ] `merger/lenskit/tests/test_retrieval_index.py`
  - [ ] `merger/lenskit/tests/test_dump_retrieval.py`
- [ ] Algorithmus umsetzen:
  - [ ] `content = chunk.get("content")`
  - [ ] Fallback: `content = resolve_range_ref(content_range_ref, artifact_dir)`
  - [ ] Hash prüfen: `sha256(canonical_md_bytes[start_byte:end_byte]) == ref.content_sha256`; erst danach wird der Byte-Slice für FTS dekodiert.
  - [ ] In `chunks_fts(chunk_id, content, path_tokens)` schreiben

### Target-Proof
- [ ] Vorher/Nachher-Check:
  - [ ] `count(*)` bleibt gleich (z. B. 539).
  - [ ] `avg(length(content))` wird `> 0`.
  - [ ] `max(length(content))` wird `> 0`.

### Stop-Kriterium
- [ ] Query auf reinen Dateiinhalt liefert Treffer.

### Risiko
- [ ] Speicher-/Leak-Risiko durch echten SQLite-Content mit Redaction-Profil absichern.

---

## Arbeitspaket B — Range-Ref v2 (Optimierungsgrad 0.79)

### Problem
- [x] `start_line/end_line` in v1 potenziell missverständlich (Source vs. Artefaktachse).

### Ziel
- [ ] Zeilenachsen explizit trennen; Fehlzitate verhindern.

### Umsetzung
- [ ] Neue Schema-Datei: `merger/lenskit/contracts/range-ref.v2.schema.json`
- [ ] v2-Felder einführen:
  - [ ] `artifact_byte_start`, `artifact_byte_end`
  - [ ] `artifact_line_start`, `artifact_line_end`
  - [ ] `source_file_path`, `source_line_start`, `source_line_end`
  - [ ] `content_sha256`
- [ ] Kompatibilität:
  - [ ] v1 weiter lesbar.
  - [ ] v2 für neue Outputs bevorzugt.
  - [ ] query-result.v1 akzeptiert v1/v2.

### Tests
- [ ] `test_range_ref_v2_schema.py`
- [ ] `test_range_roundtrip_artifact_and_source_lines.py`
- [ ] `test_context_bundle_line_axes.py`

---

## Arbeitspaket C — output_health.json (Optimierungsgrad 0.84)

### Ziel
- [ ] Jeder Output erhält maschinenlesbaren Selbsttest (`<stem>.output_health.json`).

### Muss-Checks
- [ ] `manifest_present`
- [ ] `canonical_md_hash_ok`
- [ ] `chunk_index_hash_ok`
- [ ] `chunk_count`
- [ ] `sqlite_row_count`
- [ ] `fts_content_non_empty`
- [ ] `range_ref_resolution_ok`
- [ ] `sample_query_content_hit`
- [ ] `agent_pack_present` — zunächst warnend, solange Arbeitspaket D nicht umgesetzt ist; blockierend erst nach Einführung von `<stem>.agent_reading_pack.md`.
- [ ] `redaction_status_explicit`
- [ ] `verdict: pass/fail`

### CI-Fail-Kriterien
- [ ] `fts_content_non_empty == false`
- [ ] `range_ref_resolution_ok == false`
- [ ] `sqlite_row_count != chunk_count`
- [ ] `canonical_md_hash_ok == false`

---

## Arbeitspaket D — Agent Reading Pack (Optimierungsgrad 0.73)

### Ziel
- [ ] `<stem>.agent_reading_pack.md` erzeugen (50–120 KB, zitierfähig, kompakt).

### Inhalt
- [ ] Reading Policy
- [ ] Artefaktrollen
- [ ] Top-Level-Architektur
- [ ] wichtigste Entry-Points
- [ ] wichtigste Contracts
- [ ] Query-/Retrieval-Fluss
- [ ] Artifact-Lookup/Trace/Context-Lookup-Fluss
- [ ] Driftpunkte
- [ ] Output-Health-Summary
- [ ] Claim-Evidence-Map
- [ ] Top-30-Dateien mit Range-Refs

### Governance
- [ ] Klar markieren: Navigation, nicht Wahrheit.
- [ ] Manifest-Rolle: `agent_reading_pack`, Authority: `navigation_index`, Canonicality: `derived`.

---

## Arbeitspaket E — Output-Profile trennen (Optimierungsgrad 0.70)

### Ziel
- [ ] Profile nach Verwendungszweck trennen.

### Profile
- [ ] `max-private`: include_hidden=true, redact_secrets=false, full content.
- [ ] `agent-safe`: include_hidden=true, redact_secrets=true, output_health required.
- [ ] `public-review`: include_hidden=false, redact_secrets=true, keine privaten Pfade.
- [ ] `ci-diagnostic`: metadata+ranges, kein full content.

### Tests
- [ ] `test_profile_agent_safe_redacts.py`
- [ ] `test_public_review_excludes_hidden.py`
- [ ] `test_output_health_redaction_status.py`

---

## Arbeitspaket F — Claim-Evidence-Map (Optimierungsgrad 0.76)

### Ziel
- [ ] `<stem>.claim_evidence_map.json` einführen.
- [ ] Pro Claim maschinenlesbar ausweisen:
  - [ ] supported / unsupported
  - [ ] evidenztragende Artefakte + Range-Refs
  - [ ] does_not_prove
  - [ ] requires_live_check

---

## Arbeitspaket G — Architektur-Summary ausbauen (Optimierungsgrad 0.62)

### Ziel
- [ ] Summary von Statistik zu Flussdiagnose erweitern.

### Neue Abschnitte
- [ ] Entry Points
- [ ] Artifact Producers
- [ ] Artifact Consumers
- [ ] Query Pipeline
- [ ] Context Bundle Pipeline
- [ ] Runtime Cache Pipeline
- [ ] Contracts Coverage
- [ ] Unknown Cluster
- [ ] Drift Risks
- [ ] Guard Coverage

### Stop-Kriterium
- [ ] `unknown` nicht nur zählen, sondern clustern:
  - [ ] frontend-static
  - [ ] docs-normative
  - [ ] generated-artifacts
  - [ ] fixtures
  - [ ] legacy-tools

---

## Arbeitspaket H — CI-Gates für Output-Kohärenz (Optimierungsgrad 0.81)

### Ziel
- [ ] Neuer CI-Job: `output-health-validate`.

### Geplante CLI-Checks nach Implementierung:
- [ ] `python -m merger.lenskit.cli.main validate-output-health <stem>` *(geplant)*
- [ ] `python -m merger.lenskit.cli.main query --db <sqlite> "range_resolver" --expect-hit` *(geplant)*
- [ ] `python -m merger.lenskit.cli.main artifact lookup --id <known-range>` *(geplant)*

### Blockierend
- [ ] hash mismatch
- [ ] range_ref broken
- [ ] SQLite rows != chunks
- [ ] FTS content empty
- [ ] output_health missing

### Nicht blockierend
- [ ] agent_reading_pack too large
- [ ] unknown cluster above threshold
- [ ] diagnostic warnings

---

## Priorisierte PR-Reihenfolge

- [ ] **PR 1 — FTS Content Hydration**
  - [ ] `chunks_fts.content` Ø-Länge `> 0`
  - [ ] Sample-Content-Query mit Treffer
  - [ ] Hash-Verifikation erfolgreich
- [ ] **PR 2 — Output Health Artefakt**
- [ ] **PR 3 — Range-Ref v2**
- [ ] **PR 4 — Agent Reading Pack**
- [ ] **PR 5 — Safe Output Profiles**

---

## Diagnose-Gate vor Umsetzung

- [ ] Vor PR 1 zuerst Befundskript ausführen.
- [ ] Nur patchen, wenn bestätigt:
  - [ ] `chunks > 0`
  - [ ] `with_content == 0`
  - [ ] `with_content_range_ref == chunks`
  - [ ] `avg(length(content)) == 0`
  - [ ] `max(length(content)) == 0`

Reproduzierbares Befundskript:

```bash
python - <<'PY'
import json, sqlite3, pathlib

chunk = pathlib.Path("lenskit-max-260502-1126_merge.chunk_index.jsonl")
db = pathlib.Path("lenskit-max-260502-1126_merge.chunk_index.index.sqlite")

n = has_content = has_ref = 0
for line in chunk.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    o = json.loads(line)
    n += 1
    has_content += bool(o.get("content"))
    has_ref += bool(o.get("content_range_ref"))

print({"chunks": n, "with_content": has_content, "with_content_range_ref": has_ref})

con = sqlite3.connect(db)
print(con.execute(
    "select count(*), avg(length(content)), max(length(content)) from chunks_fts"
).fetchone())
PY
```

Patch für PR 1 ist nur zulässig, wenn bestätigt:

- `chunks > 0`
- `with_content == 0`
- `with_content_range_ref == chunks`
- `avg(length(content)) == 0`
- `max(length(content)) == 0`

---

## Resonanz-/Kontrastprüfung

- [ ] Deutung A prüfen: contentloser Chunk-Index ist bewusst, Builder hydriert falsch.
- [ ] Deutung B prüfen: unvollständiger Umbau, E2E-Test fehlt.
- [ ] Synthese umsetzen: Hydration + echter Generator→Index→Query-Test.

---

## Risiko / Nutzen

### Nutzen
- [ ] echte Volltextsuche
- [ ] bessere Context Bundles
- [ ] weniger Truncation-Reibung
- [ ] sauberere Agentenantworten
- [ ] weniger Pseudo-Belege
- [ ] bessere CI-Diagnostik

### Risiken
- [ ] größere SQLite-Dateien
- [ ] sensiblere Cache-Inhalte
- [ ] mögliche v2-Kompatibilitätsbrüche
- [ ] höhere Artefaktkomplexität
- [ ] Missverständnis „Agent Pack = Wahrheit"

### Gegenmaßnahmen
- [ ] SQLite-Content nur profilgesteuert (Redaction).
- [ ] Range-Ref v1 behalten.
- [ ] Agent Pack als `navigation_index` markieren.
- [ ] Output Health blockierend machen.
- [ ] Claim-Evidence-Map gegen Überschluss nutzen.

---

## Für Dummies

- [x] `merge.md` ist das vollständige Buch.
- [x] Index/Cache sind Hilfsmittel (Inhaltsverzeichnis/Suche).
- [x] Problem heute: Suchindex hat leere Inhaltsfelder.
- [ ] Ziel: Suchindex lädt/verifiziert Text aus dem kanonischen Buch (Byte-Slice-basierte Hash-Prüfung) und sucht dann wirklich Inhalte.

---

## Epistemische Leere (offene Punkte)

- [ ] Exakte Branch-Diffs für präzise Patchzeilen fehlen.
- [ ] Query-API-Laufzeitlogs für Nutzungsfehleranalyse fehlen.
- [ ] Designabsicht hinter contentlosem Chunk-Index klären.
- [ ] Secret-Policy für private Dumps als Default definieren.

---

## Belegt / plausibel / spekulativ

- [x] **Belegt:** Rollenmodell, Reading Policy, Dump-Vollständigkeit, Range-Ref-v1, Query-Claim-Boundaries, Manifest-Autoritäten.
- [x] **Lokal geprüft:** Chunk-Index ohne Inline-Content, SQLite-FTS mit leerem Content.
- [ ] **Plausibel:** Leere FTS-Felder sind Hauptursache unzuverlässiger Agentenlesequalität.
- [ ] **Spekulativ:** Agent Reading Pack reduziert ChatGPT-File-Search-Probleme signifikant (Messung erforderlich).

---

## Essenz (1-Minute-Plan)

- [ ] Hebel: SQLite-FTS aus `content_range_ref` hydratisieren.
- [ ] Entscheidung: Erst Output-Beweisfähigkeit, dann neue Features.
- [ ] Nächste Aktion: PR 1 implementieren + Hash-Prüfung (Byte-Slice-basiert) + Tests + CI-Gate gegen leere FTS-Outputs.
