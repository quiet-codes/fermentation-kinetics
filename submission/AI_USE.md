# AI use note

## AI-use note (the half-page version for the submission)

**Tool used.** An AI coding assistant (Claude, Anthropic) working in a sandboxed Linux workspace through an
agent interface. It had no access to my own computer and did not run anything on my machine. All files were
produced in that sandbox and handed to me for local saving, checking and submission.

**What the AI did.** It wrote essentially all of the Python in `src/` and `tests/`: the Phase 0 raw-data
audit, the Level 1 kinetic model and fitting driver, the Level 2 model comparison, uncertainty, carbon
balance and yield analysis, and the Level 3 optimisation, uncertainty and reporting workflow. It ran those
scripts in the sandbox, generated the tables and figures, and drafted `reports/pre_fit_observations.md`,
`reports/level1.md`, `reports/level2.md` and `reports/level3.md` from the generated tables. It also did the
debugging, the packaging scripts, and the consistency checks that compare the reports against the tables.

**What I did.** I set the task requirements and the rules the work had to follow, chose the decisions that
needed a human call when asked (the held-out run, the exclusions, fixing K_s, the CO2 floor, carrying M5
forward), reviewed the reports, and ran the project locally. Specific personal contributions are in the
editable section at the end - that section is deliberately incomplete rather than filled in on my behalf.

**How the raw data and the model-selection decision were protected.** The raw CSVs were never edited; they
are verified against `data/raw/CHECKSUMS.sha256` on every validation run. Level 1 froze the fitted
parameters with a SHA-256 before the held-out run R6 was ever loaded. Level 2 registered its candidate
models and selection rule (D-24) before fitting and froze the result as M5. Level 3 verifies those frozen
records programmatically before it does any optimisation, and R6 is never used for fitting, tuning or
optimisation. The model choice was not revisited to make the profit numbers look better.

**Independent checks.** The test suite re-derives the Level 3 economics, the completion criterion, the steam
curve and the model policy from the tables and frozen files rather than trusting stored numbers. A
separate consistency audit checks the report against the tables, and a preflight step reproduced the
Windows CRLF test failure in a Linux simulation, found the cause (pandas writing the platform line
terminator) and fixed the writers rather than the tests.

**What remains unverified.** Nothing in this project has been run on Windows by the AI: the Windows
behaviour was simulated, not executed, and actual Windows verification is still pending. The original
assignment PDF was not available to the AI, so only the extracted brief could be used and any PDF-only
requirement is unconfirmed. The Level 3 recommendations are model predictions from a frozen fit, not plant
trials. Parameter uncertainty is quantified, but predictive uncertainty, model inadequacy and run-to-run
variability are not.

**AI output was not treated as verified output.** Every number in the reports is generated from a stored
table by a script, and the tables are checked by tests and by the consistency audit. Where the AI could not
verify something it is labelled as an assumption or an unresolved item in the reports, the traceability
matrix and `handoff/DECISIONS.md`.

---

## Editable section - my own contribution (to be completed by me)

> The statements below are for me to fill in. They are intentionally left blank rather than written on my
> behalf, because the project records cannot establish what I personally did beyond running the project and
> reviewing the outputs.

- What I reviewed in detail: ____
- What I ran locally, on which machine and OS: ____
- Which numbers I re-derived or checked by hand: ____
- Which engineering choices were mine rather than the assistant's: ____
- What I changed or rejected in the AI's output: ____
- Anything I want to disclose about how I used the tool for the report text: ____

---

## Appendix - phase-by-phase history (preserved from earlier versions)

### Phase 0
- AI read `CLAUDE.md`, the brief and the three CSVs; checked schemas, units, duplicates, time grids and
  initial conditions against the run metadata.
- Wrote and ran `src/phase0_inspect.py` and `tests/test_phase0.py`; generated the Phase 0 tables and figure.
- Choices the user should review: the 2-sd flagging threshold, reading the brief's uncertainty table in row
  order, first-order independent-error propagation for carbon-balance sds, treating `n.d.` as 0, and the
  sucrose inference for the metadata columns.

### Level 1
- AI wrote `src/kinetics.py`, `src/fit.py`, `src/level1_summary.py` and `tests/test_model.py`; ran the fit,
  the R6 prediction and the sensitivities; generated the tables, figures and `reports/level1.md`.
- Choices to review: K_s = 1 g/L fixed, the 0.10 g/L CO2 floor, per-level thermal multipliers with linear
  interpolation, the parameter bounds, the multistart strategy, and the "material change" yardstick (2
  linearised standard errors) in the sensitivity section.

### Level 2
- AI registered the candidate set and selection rule before computing, then wrote `src/models.py`,
  `compare.py`, `uncertainty.py`, `plant_uncertainty.py`, `carbon_balance.py` and `tests/test_level2.py`,
  ran them, and generated `reports/level2.md`.
- Choices to review: the seven candidates, QAICc with c-hat from the most complex model, the simplicity
  tie-break, the profile threshold, jackknife settings, linearised-Gaussian parameter draws, the Monte-Carlo
  carbon balance, the identifiability labelling rule, and the fixed plant scenarios used for Level 2.

### Level 2 packaging repair
- AI inventoried the workspace, byte-compared the preserved files, added `README.md`, `requirements.txt` and
  the report generators, reconciled the traceability table, and rebuilt the Level 2 report. No analysis was
  re-run and the frozen selection was not changed.

### Task 2 (pre-Level-3 audit follow-up)
- AI verified the D-03 uncertainty mapping and the D-24 convergence condition, reproduced the Level 2
  selection in an isolated root (20/20 stages, M5 again preferred), ran CO2-floor sensitivity refits
  (both still selecting M5), and reproduced the reported local Windows test failure, which it traced to
  text I/O without an explicit encoding. It fixed the writers, not the tests.
- It recorded its own failed first reproduction attempt rather than deleting it, and documented that the
  isolated M5 refit landed on a numerically near-equivalent minimum (the R8 leave-one-out magnitude moved
  from 1629.2 to 731.1). Both facts are still visible in `outputs/audits/task2/`.

### Level 3 and final packaging
- AI wrote `src/level3.py` (policy, completion rule, economics, steam curve), `src/level3_optimize.py`
  (search, uncertainty, comparison, figures, answers), `src/make_level3_report.py`,
  `src/level3_consistency_audit.py` and `tests/test_level3.py`; ran the search over the documented grid and
  generated `reports/level3.md` and the Level 3 tables and figures.
- It also wrote the reproduction scripts (`.sh` and `.ps1`), the submission builder, the submission
  verifier, the archive builder and the final validation driver.
- Choices to review: the grid and refinement definition, the 120 h primary horizon with a 240 h diagnostic,
  the status classes for unfinished and out-of-curve batches, the Gaussian parameter-ensemble method, and
  the decision to report completed-but-outside-the-steam-curve batches without any margin.
- **Not done by the AI:** any Windows execution, any confirmation of the assignment PDF, any plant trial,
  and any of the personal statements in the editable section above.
