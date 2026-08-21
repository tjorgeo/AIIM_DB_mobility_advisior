# Managerial report (Quarto)

This folder builds two PDFs from one set of Quarto sources:

1. the **full managerial report** — all eight chapters followed by the BCG
   appendix;
2. a **standalone BCG appendix report** containing only that appendix.

Both use the same project configuration and the same
`appendices/bcg-appendix.qmd`, so the appendix is maintained in exactly one
place. The chapter structure follows `Report_Template_Managerial.docx`.

> [!NOTE]
> This is the last link in the documentation chain: the
> [root README](../README.md) runs the stack, [`backend/README.md`](../backend/README.md)
> explains how it works, [`backend/eval/README.md`](../backend/eval/README.md)
> measures it — and the evaluation figures quoted in chapter 6 come from there.

---

## Requirements

- [Quarto CLI](https://quarto.org/docs/get-started/), recent version (the build
  was verified with Quarto 1.9.38)
- a LaTeX distribution providing `xelatex` —
  [TinyTeX](https://quarto.org/docs/output-formats/pdf-engine.html#installing-tex)
  is recommended
- the **Times New Roman** font, which `_quarto.yml` configures for body text and
  headings in both PDFs
- a PDF viewer for the final visual check

Python, R and Julia are only needed if executable code blocks in those languages
are added. Quarto ships with Pandoc, so no separate Pandoc install is required,
and the repository's Python packages are not needed for the current text-only
report.

Check the toolchain:

```bash
quarto --version
xelatex --version
```

If no LaTeX distribution is present, Quarto can install one:

```bash
quarto install tinytex
```

---

## Folder structure

```text
report/
├── _quarto.yml                    # shared project and PDF configuration
├── report.qmd                     # entry point for the full report
├── bcg-appendix-report.qmd        # entry point for the BCG-only report
├── chapters/                      # one .qmd per main chapter
│   ├── 01-use-case-value-proposition.qmd
│   ├── 02-solution-concept-originality.qmd
│   ├── 03-system-architecture-implementation.qmd
│   ├── 04-workflow-documentation.qmd
│   ├── 05-scalability-extensibility.qmd
│   ├── 06-evaluation-trade-offs.qmd
│   ├── 07-reflection-learnings.qmd
│   └── 08-references-appendix.qmd
├── appendices/
│   └── bcg-appendix.qmd           # shared BCG appendix content
├── assets/                        # figures and static files
├── references.bib                 # sources in BibTeX format
└── _output/                       # generated PDFs; not version-controlled
```

`report.qmd` includes the eight chapters and then the appendix;
`bcg-appendix-report.qmd` includes only the appendix. **Change the ordering only
in those two entry points.**

---

## Editing the content

1. In `_quarto.yml`, replace the `[Team Name]` placeholder and the five team
   member entries, removing any that are unused.
2. Fill in the eight files under `chapters/`, replacing the visible
   placeholders.
3. Maintain BCG content **only** in `appendices/bcg-appendix.qmd` — the change
   then appears in both PDFs.
4. Put figures in `assets/` and include them with a relative path:

   ```markdown
   ![Architecture overview](assets/architecture-overview.png){#fig-architecture}
   ```

5. Record sources in `references.bib` and cite them in the text with
   `[@citation-key]`.
6. Update the code and video links in `chapters/08-references-appendix.qmd`.

Chapter 6 (evaluation and trade-offs) draws on the measured results in
[`backend/eval/README.md`](../backend/eval/README.md). Regenerate those figures
before quoting them if the pipeline has changed since they were recorded.

---

## Rendering

Run from the repository root.

**Full report** — chapters 1–8 followed by the BCG appendix:

```bash
quarto render report/report.qmd     # -> report/_output/report.pdf
```

**BCG appendix only** — title page plus the appendix content:

```bash
quarto render report/bcg-appendix-report.qmd   # -> report/_output/bcg-appendix-report.pdf
```

**Both in one pass:**

```bash
quarto render report
```

---

## Pre-submission checklist

1. Open both files in `report/_output/` and check for rendering errors.
2. In the full report, check chapter numbering, tables, figures, links and the
   bibliography.
3. Confirm the BCG appendix sits at the end of the full report, and that the
   standalone report contains nothing from chapters 1–8.
4. Check the font, page breaks and general readability.
5. Verify the full report stays within the template's limit of **10 pages**.
6. Make sure no placeholders remain — `[Team Name]`, `[Value]`,
   `[Team member ...]`, `REPLACE-ME`.

---

## Customisation

- Additional chapters go in `chapters/` and are included from `report.qmd`.
- Additional appendices go in `appendices/` and are included at the end of
  `report.qmd`.
- Shared PDF options — LaTeX engine, paper size, font, numbering — live in
  `_quarto.yml` under `format.pdf`.
