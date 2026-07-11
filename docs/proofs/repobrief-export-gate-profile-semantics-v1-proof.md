# RepoBrief Export Gate Profile Semantics v1 — Proof

## Gegenstand

Der Post-Merge-Selbstreview von PR #964 fand eine begrenzte, aber reale
Widersprüchlichkeit: `repobrief_profiles.py` verlangte für `public-share` und
`security-export-review` Redaction sowie einen bestandenen finalen
Post-Emit-Health-Pass. Das Agent Export Gate leitete diese beiden Pflichten
jedoch weiterhin ausschließlich aus `agent_facing` ab. Dadurch konnte der
Gate-Sidecar für diese Profile `pass` melden, während der Export-Safety-Bericht
korrekt `fail` meldete und die Gesamtfinalisierung blockierte.

Der Gesamt-Export war damit fail-closed; die einzelne Gate-Aussage war jedoch
inkonsistent und durfte nicht als verlässliche Profilkontrolle gelten.

## Änderung

- Kanonische Profile beziehen `redaction_required` und
  `post_emit_health_required` direkt aus `profile_export_semantics`.
- Legacy-Agentprofile behalten ihre bisherigen Redaction- und Post-Health-
  Pflichten über eine explizite Kompatibilitätsabbildung.
- Nicht-agentische Exportprofile prüfen ihre Profilkontrollen, ohne eine
  Zertifizierung der Agentenoberfläche zu behaupten.
- Frühabbrüche weisen die Redaction-Pflicht ebenfalls aus der zentralen
  Profilentscheidung aus.

## Dynamische Belege

Fokussierter Lauf:

```text
111 passed
```

Breiter finaler Lauf auf dem unveränderten Arbeitsstand:

```text
3688 passed, 1 skipped, 13 deselected
ruff changed-file check: pass
WebUI JavaScript: 5/5 Testdateien mit Exitcode 0
```

Realer Mini-Snapshot, Profil `public-share`, ohne Redaction:

```text
CLI rc                     1
post_emit_health           pass
agent_export_gate          fail
export_safety_report       fail
finalization errors        agent_export_gate:fail, export_safety_report:fail
```

Vor der Korrektur lieferte derselbe Negativfall für
`agent_export_gate_status` noch `pass`.

## Sicherheits- und Autoritätsgrenzen

- Das Gate prüft nur die modellierten Profilbedingungen. Es beweist keine
  vollständige Secret- oder PII-Erkennung.
- `pass` beweist weder Claimwahrheit noch Repositoryverständnis,
  Testvollständigkeit, Runtime-Korrektheit oder Regressionsfreiheit.
- Die nicht-agentischen Profile bleiben nicht-agentisch; die zusätzlichen
  Kontrollen erzeugen keine Aussage über Agententauglichkeit.
- Die vollständige CI- und Main-Nachlaufbewertung ist separat an den
  unveränderten PR-Head zu binden.
