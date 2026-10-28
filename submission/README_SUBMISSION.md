# Submission package - Fermentation kinetics from batch data (P3)

This folder is a **generated snapshot** of the project, built by `scripts/build_submission.py`.
The canonical files live in the project tree; if the two disagree, the project tree wins and the
snapshot should be rebuilt.

## What to read first

| order | file | why |
|---|---|---|
| 1 | `level3/level3.md` | Level 3 report: recommendation, economics, uncertainty, answers to the questions |
| 2 | `level1/level1.md` | kinetic model, fitting method, parameter table, held-out prediction |
| 3 | `level2/level2.md` | model comparison, parameter uncertainty and identifiability, carbon balance, ethanol yield |
| 4 | `phase0/pre_fit_observations.md` | raw-data audit and the pre-fit reading of the curves |
| 5 | `manifest.csv` | every file with its SHA-256, size and origin |
| 6 | `requirements_traceability.csv` | each assignment requirement mapped to report section, code, evidence and status |
| 7 | `worklog.md`, `AI_USE.md` | how the work was done and what the AI did or did not verify |

## Headline result

Normal October constraint (33-37 C): **195 g/L TRS at 33 C**, batch complete (TRS = 5 g/L) in
35.57 h, 86.32 g/L ethanol, **4,858.69 INR/h of cycle time** (116,608 INR/day derived equivalent)
per 170 m3 fermenter.
If the cooling water warms by 3 C and 36 C becomes the floor: **175 g/L TRS at 36 C**, 39.82 h,
3,710.13 INR/h.

## Structure

```
submission/
  README_SUBMISSION.md  SUBMISSION_CHECKLIST.md  manifest.csv  CHECKSUMS.sha256
  assignment/           the assignment brief used as the specification
  phase0/               raw-data audit outputs
  level1/               Level 1 report, parameters, held-out prediction, figures
  level2/               Level 2 report, model selection, uncertainty, carbon balance, figures
  level3/               Level 3 report, optimisation tables, figures, audit records
  source/src/           all Python source
  source/tests/         all automated tests
  data/raw/             original raw CSVs and their checksum manifest
  logs/                 preflight evidence (including the reproduced Windows CRLF failure), Task 2 evidence
  handoff/              decisions, project state, next-account prompt
  scripts/              reproduction and packaging scripts
  worklog.md  AI_USE.md  requirements_traceability.csv  requirements.txt
```

## How to reproduce

```bash
python -m pip install -r requirements.txt
python src/level3_optimize.py --stage all --n-draws 200
python src/make_level3_report.py
python src/level3_consistency_audit.py
python -m pytest -q
```

Windows: `.\scripts\reproduce_level3.ps1`.

## Status and limits (read before submitting)

* All tests pass on Linux/Python 3.11 in this sandbox. **Actual Windows execution is still pending**
  and must be run locally; only a Linux simulation of the Windows default line terminator was done.
* The original assignment PDF is unavailable; `assignment/assignment_brief.md` is the extracted brief
  and is the governing specification here. PDF-only requirements cannot be confirmed.
* The recommendation is a model prediction from a frozen fit, not an experimentally validated plant
  optimum. Parameter uncertainty is quantified; predictive uncertainty is not.
