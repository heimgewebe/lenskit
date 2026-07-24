# RBAW-V1-T004 Host-Git-Readback-Härtung v1

## Ausgangspunkt

Der Patch-Evaluation-Sidecar bindet den Workspace-Zustand vor und nach jedem
deklarierten Befehl. Dieser Readback läuft absichtlich außerhalb der
Befehlssandbox mit dem vertrauenswürdigen System-Git.

Die erste Integritätshärtung ließ jedoch die unabhängige `.git`-Struktur in der
Sandbox schreibbar und verwendete für konfigurierte Git-Filter ein gecachtes
Inventar. Ein deklarierter Befehl hätte damit nach dem Preflight neue lokale
Filter-, Ref- oder Alternates-Metadaten vorbereiten können, die erst der spätere
Host-Readback interpretiert. Der Source-Checkout blieb dabei isoliert, aber die
Evidenzgrenze des unabhängigen Evaluations-Repositories war nicht vollständig
geschlossen.

## Umsetzung

`tools/patch_evaluation_sidecar_host_readback.py` wird nach dem bestehenden
Hardening-Overlay installiert und begrenzt genau diese Grenze:

- Die unabhängige `.git`-Struktur wird innerhalb jedes deklarierten Befehls als
  eigener read-only Submount über `/workspace/.git` gelegt.
- Der Host-Readback leert vor jedem Workspace-Fingerprint das Inventar der
  konfigurierten Filtertreiber und neutralisiert damit auch erst nach dem
  Preflight sichtbare Filterdefinitionen.
- Ein belegter Git-Mutationsversuch, der am read-only Mount scheitert, wird als
  Infrastruktur-`error` klassifiziert. Ein normaler fehlgeschlagener
  Lesezugriff bleibt dagegen ein Befehls-`failed`.
- Der Producer-Digest bindet zusätzlich das Host-Readback-Overlay; die
  bestehende Vorher-/Nachher-Prüfung deckt damit auch diese Boundary-Datei ab.

## Regressionen

`tests/test_patch_evaluation_sidecar_host_readback.py` prüft:

1. Ein nach dem ersten Fingerprint hinzugefügter Clean-Filter wird beim
   Host-Readback neu inventarisiert und nicht ausgeführt.
2. Die erzeugte Bubblewrap-Policy enthält den read-only `.git`-Submount vor dem
   `--chdir`-Übergang.
3. Ein beliebiger Python-Befehl kann keine Alternates-Datei für den späteren
   Host-Readback anlegen.
4. Ein abgewiesener `git config`-Mutationsversuch bleibt ein
   Infrastrukturfehler.
5. Ein nicht mutierender `git config --get`-Fehlschlag bleibt ein gewöhnlicher
   Befehlsfehler und wird nicht überklassifiziert.

## Restgrenze

Diese Änderung schützt die Host-Git-Evidenzgrenze, ersetzt aber keine
aggregierte Produktionssandbox. Harte Gesamtbudgets für Workspace, entpackte
Checkout-Größe, RAM, CPU, PID und IO bleiben in Bureau-Issue #979 registriert.
Ein `passed`-Artefakt bleibt externe Evaluationsevidenz und ist weiterhin kein
Korrektheits-, Sicherheits- oder Mergebeweis.
