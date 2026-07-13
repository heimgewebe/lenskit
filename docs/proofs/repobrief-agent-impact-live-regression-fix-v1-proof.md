# RepoBrief Agent Impact – Live-Regression-Fix v1

## Ausgangsbefund

Die erste commitgebundene Live-Kalibrierung auf Lenskit, Grabowski und
Weltgewebe ergab:

- Baseline Target Recall: `1.0`
- Impact Target Recall: `0.6666666666666666`
- Delta: `-0.33333333333333337`
- `no_case_regression=false`
- `default_promoted=false`

Der Grabowski-Fall fragte nach
`src/grabowski_job_finalizer.py`. Die bestehende read-only Suche lieferte den
realen Test `tests/test_job_finalizer.py`; die Impact-Fläche erzeugte dagegen
nur konventionell geratene Pfade wie
`tests/test_grabowski_job_finalizer.py`.

Kanonische Messbelege liegen im Bureau unter:

- `docs/evidence/rcga-live-goldset-20260713.json`
- `docs/evidence/rcga-live-evaluation-20260713.json`
- `docs/evidence/rcga-live-calibration-receipt-20260713.md`

Bureau-Task: `RCGA-V1-T003`.

## Reparatur

### Resolved-query-Testevidenz

`agent_impact_refinement.py` liest ausschließlich die bereits aufgelöste
`source_citation_projection` des bestehenden read-only Query-Ergebnisses.
Testartige, sichere repository-relative Pfade werden als
`evidence_type=resolved_query` ergänzt.

Die Kandidaten behalten:

- `citation_id`
- `source_range`
- `range_status`
- `authority=resolved_navigation_evidence`
- `canonicality=derived`

Sie werden ausdrücklich nicht als Graphkante, Laufzeitabhängigkeit,
Testabdeckung oder Testhinlänglichkeit dargestellt.

### Pfadhygiene

Der Evaluator entfernt vor Recall- und Kontextgrößenmessung:

- leere Pfade;
- absolute Pfade;
- Backslash- oder Doppel-Slash-Mehrdeutigkeiten;
- Punkt- und Parent-Traversal-Segmente.

Damit fließen nur sinnvolle repository-relative Kandidaten in die Metrik ein.

### Kontextkompression

Zusätzlich zum Recall werden gemessen:

- Kontextpfade pro Fall;
- mittlere Baseline- und Impact-Kontextgröße;
- aggregierte Kontextpfadreduktion.

Nutzwert kann nur festgestellt werden, wenn kein Fall beim Recall regressiert
und entweder:

1. der registrierte Recall-Vorteil erreicht wird; oder
2. bei gleichem oder besserem Recall mindestens 20 Prozent Kontextpfade
   eingespart werden.

`default_promoted` bleibt unabhängig vom Ergebnis `false`.

## Tests

Der Slice testet:

- Übernahme des realen Grabowski-artigen Testpfads aus der Query-Projektion;
- Erhalt von Citation- und Range-Metadaten;
- getrennte Evidenzklassen und deterministische Reihenfolge;
- Adapterintegration ohne Write-Surface;
- Filterung leerer und unsicherer Pfade;
- Kompressionsnutzen bei recall-gleicher Ausgabe;
- Blockierung eines Nutzenurteils bei Recall-Regression trotz hoher
  Kompression;
- aktualisierten synthetischen Goldset- und Diagnosevertrag.

## Noch notwendiger Abschlussbeleg

Vor Verifikation muss derselbe vorab registrierte Drei-Repository-Goldset erneut
auf kohärenten Bundles ausgeführt werden. Der Grabowski-Fall muss
`tests/test_job_finalizer.py` wiederfinden, kein Fall darf beim Recall
regressieren, und sämtliche Commit-, Manifest-, Run-ID- und Digest-Bindungen
müssen dauerhaft dokumentiert werden.

Dieser Implementierungsnachweis allein belegt noch keine Live-Wirkung und keine
Standardbeförderung.
