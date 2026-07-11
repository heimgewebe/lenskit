# RepoBrief Release Packaging v1 — lokaler Zielbeleg

## 1. Zielbindung

- Technischer Commit: `6fe256e69b072af0c5d25e1ea0eb4dd613608510`
- Git-Baum: `7141dbc87cb48af3a1e1057dd3835c79bd7a18d2`
- Release-Version: `2.4.0-rc.1`
- Kandidat: `2.4.0-rc.1-g6fe256e69b07`
- Lizenzkennung: `LicenseRef-RepoBrief-All-Rights-Reserved`
- Distribution: `blocked_without_separate_written_permission`

Dieser Beleg bindet den lokalen Kandidatenpfad an den technischen Commit vor
Hinzufügen dieses Proof-Dokuments. PR- und Main-CI erzeugen deshalb Kandidaten
für ihre jeweils neueren Heads und sind getrennt nachzuweisen.

## 2. Deterministischer Kandidat

Zwei voneinander getrennte Ausgabeverzeichnisse wurden aus demselben sauberen
Git-Commit gebaut und mit `diff --recursive --brief` verglichen.

Ergebnis:

- Archivdateien bytegleich;
- Manifeste bytegleich;
- `SHA256SUMS` bytegleich;
- 922 verfolgte Git-Einträge;
- 923 Tar-Mitglieder einschließlich normalisiertem Wurzelverzeichnis;
- Archivgröße: 2.115.896 Byte;
- Archiv-SHA-256:
  `50a755fa97f52cc23c6083f059eed12fbc750aa6beaec202a9c2c0b75d3607af`;
- Manifest-SHA-256:
  `bc581af402e834cec7be74900ac88ee8379c42507c7b20a11c77e0f97d395fab`.

Der Source-bound-Verifier bestätigte für beide Ausgaben:

- Commit und Git-Baum;
- vollständige Pfadmenge und Dateiinhalte;
- Datei-, Ausführungs- und Symlinkmodi;
- normalisierte UID, GID, Tar- und Gzip-Zeitstempel;
- Kandidatenname aus Version und Commit;
- vier eingebettete Lockdateien samt Größe und SHA-256;
- restriktive Lizenzgrenze;
- expliziten Ausschluss der Semantik-/Torch-Erweiterung.

Das Manifest validierte gegen
`repobrief-release-candidate.v1.schema.json`.

## 3. Abhängigkeitsbeleg

Die vier Locks wurden im digestgebundenen Playwright-Python-3.12-Container
regeneriert. Vorher- und Nachher-Hashes waren identisch:

| Lock | SHA-256 |
|---|---|
| Runtime | `d977d718585a787d68c646b27f7f9add248e0e3a4b4b9b2c53ecdf4733cdf2e4` |
| Entwicklung | `92883d9c1bb09cd8940b4059b62c86c26af8a1f7683ce939e4043aa720cd5a0e` |
| Browser | `8439f7aee554a7e1d225258b9301a0ecbbbebb666fddae7a4a070cd55ed17ff1` |
| Lock-Werkzeug | `bde91235736edee6a36ade1a5ea79eca17221c9efee192557465610061d96d51` |

Alle vier Locks wurden mit `--require-hashes` in getrennte leere Zielpfade
installiert. Zusätzlich bestanden:

- `pip-tools==7.5.3`, `pip==26.1.2`, `setuptools==83.0.0` aus dem Werkzeug-Lock;
- 22 Fokusprüfungen in der isolierten Entwicklungsumgebung;
- Chromium-Runtime-Smoke mit Chromium `149.0.7827.55`;
- zehn von zehn Browser-Flows.

## 4. Fälschungs- und Governance-Prüfungen

Die fokussierte Endprüfung umfasste 130 Tests. Darin enthalten sind
Negativfälle für:

- schmutzige Git-Arbeitsbäume;
- nichtleere Ausgabeverzeichnisse;
- zusätzliche Kandidatendateien;
- manipulierte Archive und Manifeste;
- falsche Lockhashes im Manifest;
- aus dem Archiv ausbrechende Symlinks;
- unhashte oder nicht exakt gepinnte Anforderungen;
- Lockverbraucher ohne passenden Workflow-Pfadtrigger.

Zusätzlich bestanden:

- RepoBrief-Release-Contract: vier Locks, null Findings;
- Status-Truth: 92 Tasks und 92 Boardzeilen, null Findings;
- Planning-Registration-Ratchet: null Drift;
- GitHub-Actions-Pin-Check;
- Reusable-Workflow-Contract-Check;
- YAML-Parsing aller Workflows;
- repo-weiter Ruff-Ratchet.

## 5. Grenzen

Dieser Beleg etabliert nicht:

- eine öffentliche Verbreitungs- oder Open-Source-Lizenz;
- Produkt- oder Deployment-Reife;
- Laufzeitkorrektheit oder Testvollständigkeit;
- Abwesenheit von Schwachstellen;
- einen reproduzierbaren Semantik-/Torch-Stack;
- erfolgreiche PR- oder Main-CI;
- einen aktiven verpflichtenden `release-candidate`-Ruleset-Check.

Die öffentliche Lizenzentscheidung und der Semantik-Lock bleiben getrennte,
kanonisch registrierte Folgetasks.
