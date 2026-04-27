# Vibe-Lab Transfer Falsification

## Zweck

Diese Notiz verhindert, dass Vibe-Lab-Strukturen unkontrolliert nach Lenskit
übertragen werden. Sie steht vor jeder Übernahmeentscheidung im Rahmen der
Blaupause *Lenskit Artifact Integrity & Claim Discipline* und dient als
expliziter Stop-Punkt: Bevor ein neues Modul, Schema, Register oder Workflow
aus Vibe-Lab nach Lenskit wandert, muss diese Notiz erweitert oder begründet
revidiert werden.

Lenskit ist ein deterministischer Knowledge-Compiler mit klarer Zielarchitektur
(Repository → Scan → Extraction → Chunking → Indexing → Knowledge Bundle →
Query Runtime / Agents). Vibe-Lab dient als Kontrastfolie für epistemische
Disziplin, **nicht** als Modulquelle. Eine Übernahme von Strukturen ohne
explizite Falsifikation der Annahmen würde Governance-Doppelbuchhaltung
erzeugen — und Lenskit hat bereits ein funktionierendes Governance-System aus
Bundle Manifest, Contracts, Artifact Roles und Interpretation Modes.

## Falsifizierte Annahmen

### F1: Lenskit braucht ein separates Generated-Artifacts-Register

**Annahme aus Vibe-Lab-Kontext:** Eine Datei wie
`.lenskit/generated-artifacts.yml` würde alle erzeugten Artefakte zentral
listen und so Drift verhindern.

**Falsifiziert:** Lenskit besitzt diese Wahrheit bereits.

- `merger/lenskit/contracts/bundle-manifest.v1.schema.json` definiert mit
  `artifacts[].role`, `path`, `content_type`, `bytes`, `sha256`, `contract`
  und `interpretation` jeden Artefakteintrag mit Pfad, Hash, Rolle und
  Interpretationsmodus.
- `merger/lenskit/core/constants.py` (`ArtifactRole`) hält die kanonische
  Enum-Liste, die durch `merger/lenskit/tests/test_role_completeness.py`
  bidirektional gegen das Schema geprüft wird.
- `merger/lenskit/core/merge.py` (Funktion `write_reports_v2`, Helper
  `_add_artifact`) erzeugt den Manifesteintrag rollenbasiert und nutzt eine
  lokale `CONTRACT_REGISTRY`, um `interpretation.mode` deterministisch auf
  `contract` oder `role_only` zu setzen.

Ein paralleles Register würde keine zusätzliche Wahrheit hinzufügen, sondern
eine zweite Quelle, die mit dem bestehenden Bundle Manifest desynchronisieren
kann. Die korrekte Bewegung ist, das vorhandene Manifest zu härten — siehe
PR 1 in `docs/lenskit-upgrade-blaupause.md` (Bundle Manifest Authority
Hardening).

### F2: Lenskit braucht zuerst einen generischen Claim-Budget-Contract

**Annahme aus Vibe-Lab-Kontext:** Ein universeller Contract wie
`claim-budget.v1.schema.json` würde Overclaiming domänenübergreifend regeln.

**Falsifiziert:** Lenskit hat domänenspezifische Contracts, die exakt an den
Stellen greifen, an denen Beweisansprüche entstehen.

- `merger/lenskit/contracts/query-result.v1.schema.json` und
  `merger/lenskit/contracts/retrieval-eval.v1.schema.json` umrahmen die
  Claim-Surface von Retrieval und Evaluation.
- `merger/lenskit/contracts/agent-query-session.v2.schema.json` strukturiert
  Agent-Sessions als nachvollziehbare Beobachtungen, nicht als
  Wahrheitsurteile.
- Die *Epistemic Reading Charter* und das `query --explain` / `--trace`
  Output-Surface sind die natürlichen Träger für Claim-Grenzen.

Ein generischer Universalcontract wäre die abstrakteste Stelle und damit die
schwächste Stelle, um Beweisansprüche zu binden. Claim-Boundaries gehören
**in** die bestehenden Query- und Eval-Contracts (Phase 3 der Blaupause), nicht
in einen neuen Parallelcontract.

### F3: Lenskit soll früh eine write-orientierte Agent Command Chain übernehmen

**Annahme aus Vibe-Lab-Kontext:** Eine Kette aus
`read_bundle → propose_change → verify_change` würde Agenten zu
selbstmodifizierenden Akteuren machen.

**Falsifiziert:** Lenskit ist primär ein Read-, Retrieval-, Bundle- und
Query-Runtime-System.

- Die Service-Surface (`merger/lenskit/service/`,
  `merger/lenskit/contracts/artifact-lookup.v1.schema.json`,
  `trace-lookup.v1.schema.json`, `context-lookup.v1.schema.json`) liefert
  Lookups, keine Patches.
- Die Lenskit-gerechte Kette ist
  `query → resolve_bundles → build_context → emit_trace → persist_session`
  (siehe Phase 5 der Blaupause).
- Persistierte Runtime-Artefakte (`query_trace`, `context_bundle`,
  `agent_query_session`) sind Beobachtungen aus einem Lauf, keine
  Schreiboperationen am Repository.

Eine write-orientierte Kette würde Lenskit aus seinem Zweck als Knowledge-
Compiler in einen Patch-Agenten verwandeln und die Determinismus-Garantie
brechen. Agent Provenance v2.1 (Phase 5) erweitert die Read-Surface, ohne
einen Schreibpfad einzuführen.

## Übernommenes Prinzip

Vibe-Lab dient als **Kontrastmodell**, nicht als Modulquelle. Konkret bedeutet
das:

1. Begriffe wie *Index zeigt, Content beweist, Diagnose warnt, Cache
   beschleunigt, Runtime beobachtet* werden in Lenskit auf bestehende
   Strukturen abgebildet (Bundle Manifest, Two-Layer Artifact Pattern,
   PR-Schau, Runtime Artifact Store), **nicht** als neue Subsysteme
   eingeführt.
2. Neue Felder werden additiv und optional in bestehenden Contracts ergänzt
   (`authority`, `canonicality`, `regenerable`, `staleness_sensitive`,
   `claim_boundaries`). Es entstehen keine neuen Top-Level-Schemas zur
   Doppelung bereits vorhandener Wahrheit.
3. Producer-Änderungen bleiben rollenbasiert in `core/merge.py` neben der
   bestehenden `CONTRACT_REGISTRY`. Es entsteht kein paralleler
   Producer-Pfad.
4. CI-Härtung läuft phasenweise (Diagnose vor Blocking). Neue Felder werden
   erst stabil emittiert, dann validiert, dann blockierend gemacht.

## Stop-Kriterium dieser Notiz

Diese Notiz benennt mindestens drei falsifizierte Annahmen (F1–F3) und
verweist auf die konkreten Lenskit-Strukturen, die die jeweilige Übernahme
überflüssig machen. Wird in Zukunft eine weitere Übernahme erwogen, ist sie
hier entweder zu falsifizieren oder explizit zu begründen — aber niemals
implizit zu vollziehen.
