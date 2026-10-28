# NEXT ACCOUNT PROMPT (Level 3)

Continue the fermentation-kinetics project. Phases 0, Level 1 and Level 2 are complete (sandbox-verified only). Read first: `CLAUDE.md`, `docs/assignment_brief.md`, `handoff/PROJECT_STATE.md`, `handoff/DECISIONS.md` (D-10 to D-35), `worklog.md`, `reports/level1.md`, `reports/level2.md`, `outputs/tables/model_comparison.csv`, `parameter_uncertainty.csv`, `plant_prediction_uncertainty.csv`, `structure_spread.csv`.

Facts to respect in Level 3 (only when the user asks):
- The model family is `src/models.py`; M0 is the Level 1 baseline. The rule in D-24 selected **M5** (parameters in `outputs/tables/candidate_parameters.csv`), but M5 fails the leave-out-R8 test; M2 and M6 are the more robust 37 C alternatives. Ask the user which structure(s) to carry forward, or carry M5 plus M2/M6 as a structure-uncertainty band. Do not pick by plant profit.
- R6 is no longer blind. R7 is excluded from primary fits (unusual run, not proven contamination); R3 biomass is OD600-based; R4 does not close its carbon balance within 95%.
- Fixed K_s = 1 g/L is disfavoured by the data (K_s < 0.2 g/L); sensitivity is small (1-4%) but must be carried or the user must decide on D-31.
- Extrapolation flags to enforce (CLAUDE.md rule 10): times beyond 48 h; ethanol above 108 g/L; wash strength above 14% v/v (steam curve ends at 14); 33 and 36 C are interpolations of k34/k37 and beta_P (no data); 37 C has one run; the 5 g/L end-of-batch condition is not reached within 120 h for 36-37 C at 260 g/L in M5.
- Plant formula, constants and the steam curve are in `src/plant_uncertainty.py` (`margin`, `steam_per_L`); it was used only at four fixed scenarios in Level 2. Level 3 must search initial sugar 160-260 g/L and temperature 33-37 C (and the 36 C minimum scenario) and must report the uncertainty (parameters and structures) of the recommended point and of the margin difference between candidates.
- Recommended experiment (not done): one 96 h batch at 34 C / 260 g/L; see `reports/level2.md` s6.4.

First: run `pytest -q` locally (nothing has been run on the user's machine yet) and read `README.md`.

Rules: inspect real files, never invent results, run code and tests before claiming they passed, separate sandbox from local execution, update the six handoff files at the end.
