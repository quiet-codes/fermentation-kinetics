# Fermentation Kinetics Project Instructions

## Objective
Complete the supplied chemical engineering assignment in Python, level by level:
- Phase 0: Raw-data audit and pre-fitting observations.
- Level 1: Kinetic model, parameter fitting and held-out prediction.
- Level 2: Model comparison, parameter uncertainty, identifiability, carbon balance and ethanol yield.
- Level 3: Plant optimization for the 33 °C and 36 °C minimum-temperature scenarios.
- Final phase: Complete report, reproducibility checks, work log and AI-use note.

## Rules
1. Treat `docs/assignment_brief.md` as the authoritative specification.
2. Inspect actual files before drawing conclusions. Never invent measurements, results, parameters or test outcomes.
3. Preserve raw CSV files.
4. Implement kinetic ODE equations explicitly in Python. SciPy solvers and optimization libraries are permitted.
5. Complete only the phase requested. Reuse existing code instead of rebuilding the project.
6. Justify every exclusion of a run using independent experimental or chemical evidence.
7. Keep the held-out run completely separate from model fitting and tuning.
8. Report uncertainty and identifiability honestly.
9. Calculate carbon balance for all eight runs.
10. Follow all plant constraints and flag unsupported extrapolations.
11. Run code and tests before claiming they passed.
12. Keep the report consistent with generated tables and plots.

## Handoff rules
At the end of each phase, update:
- `worklog.md`
- `AI_USE.md`
- `docs/requirements_traceability.csv`
- `handoff/PROJECT_STATE.md`
- `handoff/DECISIONS.md`
- `handoff/NEXT_ACCOUNT_PROMPT.md`

Keep the raw files, source code, generated outputs and decisions together. Report completed work, failed checks and unresolved limitations accurately.