# Forensic Preflight Calibration Proof

> Erstellt am 2026-06-01.  
> Scope: Lenskit F2c — nicht-blockierende Kalibrierung von
> `governance forensic-preflight` gegen lokal erzeugte echte Lenskit-Bundles.

## 1. Scope

Dieser Proof eicht das diagnostische Verhalten von
`python3 -m merger.lenskit.cli.main governance forensic-preflight --manifest <manifest> --json`
gegen echte, durch die bestehende Merge-Pipeline erzeugte Bundle-Artefakte.

Der Slice erzeugt **kein** CI-Gate und promoted `forensic_strict` **nicht** zu
einem blockierenden Workflow. Er misst, ob formale Preflight-Signale auf realen
Bundles stabil unterscheidbar sind.

## 2. Prämissencheck

Vor dem Patch wurden folgende Prämissen geprüft:

- `merger/lenskit/core/forensic_preflight.py` existiert.
- `merger/lenskit/core/post_emit_health.py` prüft `claim_evidence_map_json` auf
  Presence, Hash und Schema.
- `merger/lenskit/tests/test_forensic_preflight.py` existiert.
- `find .github/workflows -maxdepth 1 -type f -iname '*forensic*' -print`
  lieferte keine Treffer; es gibt weiterhin keinen forensic-spezifischen
  Workflow.
- Die vorab gelesenen Architektur-/Proof-Dokumente definieren
  `claim_evidence_map_json` als referenz-only Navigations-/Evidence-Index und
  `forensic_strict` als preflight-gated Diagnoselevel, nicht als
  Wahrheitsentscheidung.

## 3. Diagnose vor Patch

Der lokale Diagnose-Lauf vor dem Patch erzeugte ein reales Bundle über
`scan_repo(...)` + `write_reports_v2(...)` und schrieb anschließend
`post_emit_health`.

Erste Beobachtung: Wenn `scan_repo(..., max_bytes=0)` verwendet wurde, enthielt
das reale Bundle zwar `canonical_md`, `claim_evidence_map_json`,
`output_health` und `agent_reading_pack`, aber **kein** `chunk_index_jsonl` und
**kein** `citation_map_jsonl`. `forensic-preflight` blockierte folgerichtig auf
`chunk_index_hash_ok`, `citation_map_hash_ok`, `range_citation_strict` und
`no_required_checks_skipped`.

Kalibrierung: Mit `scan_repo(..., max_bytes=100_000)` erzeugte dieselbe reale
Pipeline ein Bundle mit den für den Positivfall nötigen Rollen:

- `canonical_md`
- `chunk_index_jsonl`
- `citation_map_jsonl`
- `claim_evidence_map_json`
- zusätzlich u. a. `agent_reading_pack`, `dump_index_json`,
  `index_sidecar_json`, `output_health`, `retrieval_eval_json`, `sqlite_index`

Das persistierte `post_emit_health` war an denselben Manifestpfad und dieselbe
`run_id` gebunden.

## 4. Nicht-blockierender Kalibrierungs-Harness

Neuer Harness:

```bash
bash scripts/proofs/forensic_preflight_calibration.sh
```

Der Harness:

1. erzeugt ein temporäres Fixture-Repository,
2. erzeugt daraus über die bestehende Merge-Pipeline ein reales Bundle,
3. schreibt `post_emit_health`,
4. führt `governance forensic-preflight --json` über die CLI aus,
5. speichert JSON-Ergebnisse in einem temporären `results/`-Verzeichnis,
6. prüft einen Positivfall und drei negative Kalibrierungsfälle.

Die erzeugten Artefakte bleiben standardmäßig in einem `mktemp`-Verzeichnis und
werden nicht committet. Für manuelle Forensik kann
`LENSKIT_FORENSIC_CALIBRATION_KEEP=1` gesetzt werden.

## 5. Testmatrix der realen Läufe

| Fall | Manipulation | Erwartung | Gemessener Status | Zentrale Checks |
| :--- | :--- | :--- | :--- | :--- |
| A Positivfall | echtes Bundle mit `canonical_md`, `chunk_index_jsonl`, `citation_map_jsonl`, `claim_evidence_map_json`; `post_emit_health` gebunden | `pass` oder begründetes `blocked` bei Umgebungslimit | `pass` | alle formalen Pflichtchecks `pass` |
| B Fehlende Claim-Map | `claim_evidence_map_json` aus dem Manifest entfernt; `post_emit_health` neu an dieses Manifest gebunden | `blocked` | `blocked` | `claim_evidence_map_present=blocked`, `claim_evidence_map_hash_ok=blocked`, `claim_evidence_map_schema_valid=blocked` |
| C Stale post_emit_health | `post_emit_health.bundle_manifest_path` und `bundle_run_id` auf andere Werte gesetzt | `fail` oder `blocked`, niemals `pass` | `fail` | `post_emit_health_bound_to_manifest=fail`, abhängige Checks `blocked` |
| D Hash-Drift | `claim_evidence_map_json` nach Manifest-/post_emit_health-Erzeugung manipuliert | Hash-Check `fail`, Schema höchstens `skipped`, Gesamtstatus nicht `pass` | `fail` | `claim_evidence_map_hash_ok=fail`, `claim_evidence_map_schema_valid=skipped` |

## 6. Repräsentativer Harness-Output

Der lokale Lauf vom 2026-06-01 lieferte zusammengefasst:

```json
{
  "positive_roles": [
    "agent_reading_pack",
    "canonical_md",
    "chunk_index_jsonl",
    "citation_map_jsonl",
    "claim_evidence_map_json",
    "derived_manifest_json",
    "dump_index_json",
    "index_sidecar_json",
    "output_health",
    "retrieval_eval_json",
    "sqlite_index"
  ],
  "post_emit_health_bound": true,
  "cases": {
    "positive": {"status": "pass", "cli_exit_code": 0},
    "missing_claim_map": {"status": "blocked", "cli_exit_code": 2},
    "stale_post_emit_health": {"status": "fail", "cli_exit_code": 2},
    "hash_drift": {"status": "fail", "cli_exit_code": 2}
  }
}
```

## 7. Warum keine CI-Promotion

Die Kalibrierung zeigt, dass die Preflight-Signale für die vier Pflichtfälle
unterscheidbar sind. Sie zeigt **nicht**, dass ein blockierendes CI-Gate schon
policy-stabil wäre.

Gründe gegen eine direkte Promotion in diesem PR:

- Der Positivfall hängt sichtbar von realen Bundle-Parametern ab
  (`max_bytes=100_000` erzeugt die strikten Navigationsartefakte; `max_bytes=0`
  blockiert formal korrekt).
- `forensic-preflight` ist ein Diagnoseinstrument für formale Voraussetzungen.
- Die Fehlersemantik soll erst über mehrere reale Läufe stabil beobachtet werden,
  bevor ein Workflow blockierend wird.
- Capability-degradierte Hosts können je nach Profil weiterhin niedrigere
  Evidence-Level verlangen.

## 8. Grenzen

Ein `pass` bedeutet ausschließlich, dass die geprüften formalen Voraussetzungen
des Preflights erfüllt sind.

Ein `pass` bedeutet ausdrücklich nicht:

- Claims sind wahr.
- Das Repository wurde semantisch verstanden.
- Eine Antwort ist ohne Citation-/Range-Belege sicher.
- Die Claim-Evidence-Map ersetzt die Citation Map.
- Freie Claim-Extraktion, Support-Bewertung oder Provenance-Verdict wurden
  durchgeführt.

## 9. Entscheidung / nächster Gate-Punkt

CI-Promotion bleibt offen. Ein Folge-PR kann erst dann entscheiden, ob
`forensic_strict` optional in CI promoted wird, wenn mindestens **drei** reale,
erfolgreiche Positivläufe und stabile negative Fehlersignale über unterschiedliche
Bundle-Profile dokumentiert sind.

Bis dahin gilt: Das Thermometer ist geeicht; es ist noch kein Richter.
