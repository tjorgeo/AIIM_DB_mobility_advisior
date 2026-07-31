# Managerial Reports mit Quarto

Dieser Ordner enthält zwei PDF-Reports:

1. den vollständigen Managerial Report mit allen acht Kapiteln und dem
   BCG-Appendix am Ende;
2. einen eigenständigen PDF-Report, der ausschließlich den BCG-Appendix enthält.

Die Kapitelstruktur des vollständigen Reports basiert auf
`Report_Template_Managerial.docx`. Beide PDFs verwenden dieselbe
Projektkonfiguration und dieselbe Datei `appendices/bcg-appendix.qmd`, sodass der
Appendix nur an einer Stelle gepflegt werden muss.

## Requirements

Erforderlich sind:

- [Quarto CLI](https://quarto.org/docs/get-started/) in einer aktuellen Version
  (der Build wurde mit Quarto 1.9.38 geprüft);
- eine LaTeX-Distribution mit `xelatex`; empfohlen wird
  [TinyTeX](https://quarto.org/docs/output-formats/pdf-engine.html#installing-tex);
- die Schriftart **Times New Roman**, da sie für Fließtext und Überschriften
  beider PDFs in `_quarto.yml` konfiguriert ist;
- ein PDF-Viewer für die finale Sichtprüfung;
- optional Python, R oder Julia, aber nur wenn ausführbare Codeblöcke dieser
  Sprache ergänzt werden.

Quarto und die LaTeX-Engine lassen sich so prüfen:

```bash
quarto --version
xelatex --version
```

Falls noch keine LaTeX-Distribution vorhanden ist, kann Quarto TinyTeX
installieren:

```bash
quarto install tinytex
```

Quarto bringt Pandoc mit. Eine separate Pandoc-Installation und die
Python-Pakete des Repositorys sind für den aktuellen, rein textbasierten Report
nicht erforderlich.

## Ordnerstruktur

```text
report/
├── _quarto.yml                    # Gemeinsame Projekt- und PDF-Konfiguration
├── report.qmd                     # Einstiegspunkt für den vollständigen Report
├── bcg-appendix-report.qmd        # Einstiegspunkt für den BCG-Report
├── chapters/                      # Eine QMD-Datei je Hauptkapitel
├── appendices/
│   └── bcg-appendix.qmd           # Gemeinsamer Inhalt des BCG-Appendix
├── assets/                        # Abbildungen und statische Dateien
├── references.bib                 # Quellen im BibTeX-Format
└── _output/                       # Generierte PDFs; wird nicht versioniert
```

`report.qmd` bindet zuerst die acht Kapitel und anschließend
`appendices/bcg-appendix.qmd` ein. `bcg-appendix-report.qmd` bindet nur diesen
Appendix ein. Die Reihenfolge sollte ausschließlich in den beiden
Einstiegspunkten geändert werden.

## Inhalte bearbeiten

1. In `_quarto.yml` den Platzhalter `[Team Name]` und die fünf Teammitglieder
   ersetzen. Nicht benötigte Autoreneinträge entfernen.
2. Die Inhalte in den acht Dateien unter `chapters/` ergänzen und sichtbare
   Platzhalter ersetzen.
3. Den BCG-Inhalt ausschließlich in `appendices/bcg-appendix.qmd` pflegen. Die
   Änderung erscheint dadurch in beiden PDF-Ausgaben.
4. Abbildungen unter `assets/` ablegen und mit einem relativen Pfad einbinden:

   ```markdown
   ![Architecture overview](assets/architecture-overview.png){#fig-architecture}
   ```

5. Literatur in `references.bib` im BibTeX-Format erfassen und im Text mit
   `[@citation-key]` zitieren.
6. Code- und Videolink in
   `chapters/08-references-appendix.qmd` aktualisieren.

## Vollständigen Report als PDF erzeugen

Aus dem Repository-Root:

```bash
quarto render report/report.qmd
```

Ergebnis:

```text
report/_output/report.pdf
```

Dieser Report enthält die Kapitel 1–8 und danach den BCG-Appendix.

## Nur den BCG-Appendix als PDF erzeugen

Aus dem Repository-Root:

```bash
quarto render report/bcg-appendix-report.qmd
```

Ergebnis:

```text
report/_output/bcg-appendix-report.pdf
```

Dieser Report enthält neben der Titelseite ausschließlich den Inhalt aus
`appendices/bcg-appendix.qmd`.

Optional können beide PDFs in einem Durchlauf erzeugt werden:

```bash
quarto render report
```

## Prüfung vor der Abgabe

1. Beide Dateien unter `report/_output/` öffnen und auf Renderfehler prüfen.
2. Im vollständigen Report Kapitelnummerierung, Tabellen, Abbildungen, Links
   und Literaturverzeichnis prüfen.
3. Kontrollieren, dass der BCG-Appendix im vollständigen Report am Ende steht
   und der eigenständige Report keinen Inhalt aus den Kapiteln 1–8 enthält.
4. Schriftart, Seitenumbrüche und Lesbarkeit kontrollieren.
5. Für den vollständigen Report die in der ursprünglichen Vorlage genannte
   Grenze von **maximal 10 Seiten** prüfen.
6. Sicherstellen, dass keine Platzhalter wie `[Team Name]`, `[Value]`,
   `[Team member ...]` oder `REPLACE-ME` verbleiben.

## Anpassungen

- Weitere Hauptkapitel werden unter `chapters/` angelegt und in `report.qmd`
  eingebunden.
- Weitere Appendix-Dateien werden unter `appendices/` angelegt und am Ende von
  `report.qmd` eingebunden.
- Gemeinsame PDF-Optionen wie LaTeX-Engine, Papierformat, Schrift und
  Nummerierung stehen in `_quarto.yml` unter `format.pdf`.
