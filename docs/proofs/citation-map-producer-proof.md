# Citation-Map-Producer — Real-Dump-Proof

**Datum:** 2026-05-13
**Status:** ⛔ STOP — Producer-Real-Dump-Proof nicht erbracht
**Producer-Status im Code:** nicht implementiert
**Roadmap-Status:** `[ ]` bleibt offen

---

## TL;DR

Der Producer für `citation_map_jsonl` wurde in diesem PR **nicht** implementiert.

Begründung: Das einzige in der Aufgabe akzeptierte Beleg-Artefakt — ein
**repolens/iPad-Dump** — ist im Arbeitsumfeld nicht verfügbar. Damit greift das
explizite Stop-Kriterium aus der Aufgabenstellung:

> Stop, wenn der aktuelle repolens/iPad-Dump nicht lokal verfügbar ist.

Ein Producer-Patch ohne Target-Proof würde zwingend gegen die
Diagnose-first-Regel verstoßen oder sich auf interpolierte Quellen stützen
(Pfade, `repo_id`, `snapshot`, Chunk-Zahlen). Beides ist laut Aufgabe untersagt.

Ein sauberer STOP wird hier einem „scheinbar grünen Producer mit interpolierten
Quellen" vorgezogen, wie die Aufgabe es ausdrücklich verlangt.

---

## Geprüfter Kontext (repo-belegt)

Vor der Stop-Entscheidung wurde der folgende Kontext gelesen und verifiziert:

| Beleg | Pfad | Befund |
|---|---|---|
| Roadmap | `docs/roadmap/lenskit-master-roadmap.md` | Producer-Eintrag steht offen (`[ ]`); Blocker dokumentiert |
| Vorbedingungs-Diagnose | `docs/proofs/citation-map-producer-diagnosis.md` | Stop-Diagnose von 2026-05-12; Helper-Vorbedingung erledigt |
| Validator-Real-Dump-Proof | `docs/proofs/citation-readiness-validator-proof.md` | PASS gegen den Vorgänger-Dump (rlens/Heim-PC), **nicht** repolens/iPad |
| Citation-Map-Contract | `merger/lenskit/contracts/citation-map.v1.schema.json` | Pflichtfelder: `citation_id`, `repo_id`, `snapshot`, `canonical_range` (mit `start_byte`, `end_byte`, `start_line`, `end_line`, `content_sha256`) |
| Bundle-Manifest-Contract | `merger/lenskit/contracts/bundle-manifest.v1.schema.json` | Für `citation_map_jsonl` erzwingt: `content_type=application/x-ndjson`, `contract={id:citation-map,version:v1}`, `authority=navigation_index`, `canonicality=derived`, `regenerable=true`, `staleness_sensitive=true` |
| Manifest-Wiring | `merger/lenskit/core/merge.py:5891` (`_add_artifact`), `merge.py:5824` (CONTRACT_REGISTRY), `merge.py:5833` (AUTHORITY_REGISTRY) | Wiring-Punkt vorhanden, kein Eintrag für `CITATION_MAP_JSONL` |
| ArtifactRole | `merger/lenskit/core/constants.py:21` | `CITATION_MAP_JSONL = "citation_map_jsonl"` vorhanden |
| Citation-Id-Helper | `merger/lenskit/core/citation_id.py` | `make_citation_id(...)` einsatzbereit |
| Validator | `merger/lenskit/core/citation_validate.py` | als Konsument einsatzbereit |

Alle aufgeführten Bausteine sind vorhanden. Es fehlt ausschließlich das, was
laut Aufgabe zwingend nötig ist: ein **belegbarer repolens/iPad-Dump**.

---

## Diagnose: Verfügbarkeit des repolens/iPad-Dumps

Ziel: einen real erzeugten repolens/iPad-Bundle finden, der enthält
- ein `*.bundle.manifest.json` mit `kind=repolens.bundle.manifest`,
- die zugehörige `canonical_md`,
- den zugehörigen `chunk_index_jsonl`,
- und Sidecars, die `repo_id` sowie `snapshot.run_id` /
  `snapshot.canonical_md_path` / `snapshot.canonical_md_sha256` belegen.

### Durchgeführte Suchen

```bash
# 1) Repo-internes data/ wie in der Vorbedingungs-Diagnose erwartet
ls -la /home/user/lenskit/data/
#   -> nur .gitkeep, leeres Verzeichnis

# 2) Sandbox-/tmp-Pfade (wo der frühere rlens-Dump lag)
ls /tmp/lenskit-hub/merges/ 2>/dev/null
#   -> Verzeichnis existiert nicht

# 3) Systemweite Suche nach typischen Bundle-Dateinamen
find / -maxdepth 8 \
  \( -name "*.bundle.manifest.json" \
     -o -name "*.merge.md" \
     -o -name "*.chunk_index.jsonl" \
     -o -name "*.dump_index.json" \) 2>/dev/null
#   -> kein Treffer

# 4) Suche nach repolens-/iPad-spezifischen Pfaden
find / -type d -name "repolens" 2>/dev/null
find / -type f -name "*iPad*" 2>/dev/null
#   -> kein einschlägiger Treffer (nur ipaddr-Ruby-Gems)
```

### Befund

| Pfadklasse | Befund |
|---|---|
| `/home/user/lenskit/data/` | leer (`.gitkeep`) |
| `/tmp/lenskit-hub/merges/` | nicht existent |
| systemweite `*.bundle.manifest.json` | keine Treffer |
| systemweite `*.chunk_index.jsonl` außerhalb Repo-Tests | keine Treffer |
| systemweite `*.merge.md` | keine Treffer |
| Verzeichnis `repolens` als Dump-Quelle | nicht vorhanden |
| Verzeichnis `iPad` / `iPad-*` als Dump-Quelle | nicht vorhanden |

Damit ist **kein repolens/iPad-Dump** lokal verfügbar.

---

## Warum kein Fallback auf den alten rlens/Heim-PC-Dump

Die Aufgabe verbietet ausdrücklich:

> Der neue Dump ist repolens/iPad, nicht der alte rlens/Heim-PC-Dump.
> Alte konkrete Werte wie `585`, `594`, alte `/tmp`-Pfade oder alte Dump-Stems
> dürfen nicht übernommen werden.

Damit ist insbesondere ausgeschlossen:

- der `/tmp/lenskit-hub/merges/`-Pfad aus dem Validator-Proof
  (`docs/proofs/citation-readiness-validator-proof.md`),
- der Stem `lenskit-max-260513-1503_merge`,
- die dort gemessenen Chunk-Zahlen,
- die dort gelisteten SHA256-Werte.

Eine Inline-Regeneration eines neuen rlens-Dumps wäre ebenfalls **nicht** der
geforderte repolens/iPad-Dump. Sie würde:

- `repo_id` aus dem Sandbox-Klon dieses Repos ableiten (nicht belegbar als
  repolens/iPad-Identität),
- `snapshot.run_id` aus einer frisch generierten Run-ID erzeugen, die keinen
  iPad-Bezug hat,
- eine zweite Quelle der Wahrheit für Chunk-Zahlen/SHA-Werte schaffen, die
  zwangsläufig vom echten repolens/iPad-Dump abweicht.

Beides scheitert an der Diagnose-first-Regel und am Verbot von Interpolation
bei `repo_id`, `snapshot`, Pfaden und Chunk-Zahlen.

---

## Hypothesen vor Stop-Entscheidung

Drei Hypothesen wurden geprüft. Keine konnte den fehlenden Dump ersetzen.

### H1: Ein repolens/iPad-Dump liegt unter `/home/user/lenskit/data/` oder einem dokumentierten externen Pfad.
- Check 1: `ls -la /home/user/lenskit/data/` → nur `.gitkeep`.
- Check 2: systemweite Suche nach `*.bundle.manifest.json` → kein Treffer.
- Check 3: Repo-Doku (`docs/proofs/citation-map-producer-diagnosis.md`) nennt
  `data/` als Sollort und attestiert „leer".
- Ergebnis: **H1 widerlegt.**

### H2: Ein repolens/iPad-Dump kann aus dem aktuellen Repo lokal regeneriert werden, ohne `repo_id`/`snapshot` zu interpolieren.
- Check 1: `repo_id` und `snapshot.run_id` müssen belegbar sein. In diesem
  Sandbox-Klon ist weder eine iPad-spezifische `repo_id` belegt noch eine
  iPad-spezifische `run_id`.
- Check 2: Der Validator-Proof zeigt, dass eine lokale Merger-Ausführung im
  Sandbox-Container einen Bundle erzeugt, der aber **rlens/Heim-PC-Semantik**
  trägt (`run_id`-Stem `lenskit-…`, kein iPad-Bezug).
- Check 3: Aufgabe verbietet ausdrücklich, alte Stems/`/tmp`-Pfade zu
  übernehmen. Ein neu generierter rlens-Stem wäre wieder kein
  repolens/iPad-Dump.
- Ergebnis: **H2 widerlegt** — Regeneration löst das Quellenproblem nicht,
  sondern verschiebt es nur.

### H3: Der Producer kann auf einem synthetischen Fixture-Bundle plus Stop-Vermerk für den Real-Dump-Proof PASS-gestellt werden.
- Check 1: Aufgabe schreibt: „PASS nur bei … keine offenen Quellen für
  `repo_id` oder `snapshot`."
- Check 2: Aufgabe schreibt: „Ein sauberer STOP ist akzeptabler als ein
  scheinbar grüner Producer mit interpolierten Quellen."
- Check 3: Die Roadmap koppelt `[x]` explizit an „echter PASS"; eine
  Fixture-PASS hebt den Producer-Eintrag nicht.
- Ergebnis: **H3 widerlegt** — Fixture-Tests sind kein Ersatz für den
  geforderten Real-Dump-Proof.

---

## Erfüllte Stop-Kriterien

Aus der Stop-Kriterienliste der Aufgabe sind die folgenden eindeutig erfüllt:

| Kriterium | Erfüllt? | Belege |
|---|---|---|
| repolens/iPad-Dump nicht lokal verfügbar | **Ja** | siehe Such-Sektion oben |
| `repo_id` nicht eindeutig belegbar | **Ja** | keine Dump-/Manifest-/Sidecar-Quelle vorhanden |
| `snapshot` nicht eindeutig belegbar | **Ja** | keine Manifest-/Sidecar-Quelle vorhanden |
| Schema-Pflichtfelder nicht befüllbar | **Ja** | `citation_id` setzt `canonical_md_sha256` und Range-Bytes des realen Dumps voraus |
| Real-Dump-Proof nicht reproduzierbar | **Ja** | ohne Dump nicht reproduzierbar |

Es genügt **ein** hartes Stop-Kriterium, um den Patch nicht zu finalisieren.
Hier sind **fünf** erfüllt.

---

## Was diesem Stop fehlt zum PASS

Ein späterer Producer-PASS benötigt zwingend:

1. **repolens/iPad-Dump im Arbeitsumfeld**, mit
   - `*.bundle.manifest.json` (`kind=repolens.bundle.manifest`, `version=1.0`),
   - `canonical_md`-Datei,
   - `chunk_index_jsonl` mit dual ranges (`canonical_range`, `source_range`,
     `content_range_ref`),
   - belegbarer Quelle für `repo_id`,
   - belegbarer Quelle für `snapshot.run_id` und
     `snapshot.canonical_md_path` (Schema verlangt beides).

2. **Eindeutige `repo_id`-Quelle** aus dem Dump:
   - Bundle-Manifest, Sidecar oder explizite Producer-Konfiguration.
   - Nicht aus Dateinamen ableiten, solange eine bessere Quelle existiert.

3. **Eindeutige `snapshot`-Quelle** aus dem Dump:
   - `run_id` aus dem Bundle-Manifest,
   - `canonical_md_path` aus dem Manifest-Eintrag mit Rolle `canonical_md`,
   - `canonical_md_sha256` aus demselben Manifest-Eintrag (gegen tatsächlichen
     SHA-Wert geprüft).

4. **Producer-Datei** `merger/lenskit/core/citation_map.py` (pure Funktion +
   IO-Adapter), die je Chunk mit gültigem `canonical_range` genau eine Zeile
   erzeugt:
   - `citation_id` ausschließlich via `make_citation_id(...)`,
   - `repo_id` und `snapshot` aus den oben belegten Quellen,
   - `canonical_range` inklusive `start_line`/`end_line`, bytegenau aus
     `canonical_md` berechnet.

5. **Manifest-Wiring** in `merge.py`:
   - Eintrag im `CONTRACT_REGISTRY` mit `{id:citation-map,version:v1}`,
   - Eintrag im `AUTHORITY_REGISTRY` mit `authority=navigation_index`,
     `canonicality=derived`, `regenerable=true`, `staleness_sensitive=true`,
   - `_add_artifact(...)` für `ArtifactRole.CITATION_MAP_JSONL` mit
     `content_type="application/x-ndjson"`.

6. **Tests** für: Entry-Erzeugung, `make_citation_id`-Pflicht,
   Line-Range-Berechnung, Schema-Validität der Zeilen, Manifest-Wiring (Rolle,
   SHA, Bytes), expliziter Fehler bei fehlender `repo_id`/`snapshot`-Quelle,
   `citation_map_jsonl` darf nie als `canonical_content` oder `content_source`
   klassifiziert werden.

7. **Aktualisierter Real-Dump-Proof** mit allen geforderten Feldern
   (Dump-Stem, Pfade, `run_id`, Quellenangaben, Manifest- und Actual-SHAs für
   `canonical_md`/`chunk_index_jsonl`/`citation_map_jsonl`, `chunk_count`,
   `valid_chunk_count`, `citation_map_row_count`, `citation_id_count`,
   `citation_id_duplicate_count`, drei Beispielzeilen).

Erst wenn alle sieben Punkte erfüllt sind, darf der Roadmap-Eintrag auf `[x]`
gehoben werden.

---

## Roadmap-Implikation

In `docs/roadmap/lenskit-master-roadmap.md` bleibt sowohl

> `- [ ] Citation-Map-Producer, geplante Citation-/Evidence-Health-Prüfung in separater Folge-PR, Real-Dump-Proof`

als auch

> `- [ ] Citation-Map-Producer plus eigener Producer-Real-Dump-Proof`

unverändert offen. Die Roadmap wird ausschließlich um einen Verweis auf
dieses STOP-Dokument ergänzt — kein Status-Flip auf `[x]`.

---

## Invarianten dieses Stops

- Kein Producer-Code geschrieben.
- Kein Manifest-Wiring geändert.
- Kein Eintrag im `CONTRACT_REGISTRY` oder `AUTHORITY_REGISTRY` ergänzt.
- Kein neuer Test geschrieben, der einen nicht existenten Producer prüft.
- Keine Werte aus dem alten rlens/Heim-PC-Validator-Proof als Wahrheit
  übernommen (keine Chunk-Zahlen, keine SHAs, keine `/tmp`-Pfade, kein Stem).
- `citation_map_jsonl` bleibt im Repo-Inventar **nicht** als kanonisches
  Artefakt definiert.

---

## Entscheidungsgrad

| Aspekt | Sicherheit |
|---|---|
| repolens/iPad-Dump fehlt im Arbeitsumfeld | sehr hoch (0.98) |
| Stop-Kriterium „Dump nicht lokal verfügbar" erfüllt | sehr hoch (0.98) |
| Kein interpolierbarer Ersatz für `repo_id`/`snapshot` ohne Dump | hoch (0.95) |
| Fixture-PASS würde Roadmap-Gate nicht heben | sehr hoch (0.98) |

---

**Dokument-Version:** 1.0
**Diagnose durchgeführt:** 2026-05-13
**Nächste Bewertung:** sobald ein repolens/iPad-Dump im Arbeitsumfeld liegt
**Status:** ⛔ Stop, kein Producer-Patch, nur Dokumentation
