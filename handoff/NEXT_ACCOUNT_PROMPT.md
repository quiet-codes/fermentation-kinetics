# NEXT ACCOUNT PROMPT (post-Level-3 / final submission)

The project is complete through Level 3 and final packaging. Read first: `CLAUDE.md`,
`docs/assignment_brief.md`, `handoff/PROJECT_STATE.md`, `handoff/DECISIONS.md` (D-37 to D-45 are Level 3),
`worklog.md`, `reports/level3.md`, `outputs/audits/level3/consistency_report.md`.

Facts to respect if work continues:

- **Frozen policy.** M5 under D-24 remains the primary model; the parameter set is
  `outputs/tables/work/fit_M5.json` (`M5_a29043ff3379ad5d`). R6 is held out and must never be used for fitting,
  tuning or optimisation. `src/level3.py::verify_model_policy` must pass before any new optimisation runs.
- **Feasibility rules.** A batch is complete only at residual TRS <= 5 g/L (first crossing, interpolated).
  Unfinished batches get no completion time and no margin. The steam curve covers only 7-14 % v/v wash;
  outside it there is no steam cost and no margin. Do not relax either rule to improve the apparent optimum.
- **Current recommendation.** 195 g/L TRS at 33 C (4,858.69 INR/h); 175 g/L at 36 C (3,710.13 INR/h) in the
  warm scenario. M2/M6 own optima sit one grid step lower in sugar and 4-5 % higher in margin; they are
  comparisons, not replacements.
- **Reproduction.** `python src/level3_optimize.py --stage all --n-draws 200`, then
  `python src/make_level3_report.py`, then `python src/level3_consistency_audit.py`, then `python -m pytest -q`.
  On Windows use `scripts/reproduce_level3.ps1`. Never hand-edit `outputs/tables/` or `reports/level3.md`.
- **Packaging.** `submission/` and the final ZIP are generated output; rebuild with
  `scripts/build_submission.py`, `scripts/verify_submission.py`, `scripts/create_final_zip.py`.

Still outstanding (not the AI's to claim):
- Actual Windows execution of the tests and the PowerShell reproduction script.
- The original assignment PDF, so PDF-only requirements stay unconfirmed.
- The student's personal-contribution section in `AI_USE.md`.

Rules: inspect the real files, never invent results, run code and tests before claiming they passed, keep
sandbox and Windows evidence separate, and update the six handoff files at the end of any phase.
