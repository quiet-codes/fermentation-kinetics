# AI use note

**Tool:** Claude (Anthropic, Claude Sonnet 5.5), claude.ai chat, Free plan. No access to the user's computer or VS Code; files were produced in a sandbox and handed over for local saving.

## Phase 0 – what the AI did
- Read `CLAUDE.md`, the assignment brief and the three CSVs; checked schemas, units, duplicates, time grids, initial conditions vs metadata.
- Wrote `src/phase0_inspect.py` and `tests/test_phase0.py`; ran both in a sandbox (script ran; 6 tests passed).
- Generated the tables and figure; drafted the observation report, worklog, traceability table and handoff files.
- Made analytical choices that the user should review: 2-sd flagging threshold; reading the brief's uncertainty table in row order; first-order, independent-error propagation for carbon-balance sds; treating n.d. as 0; the ~70% sucrose inference for the metadata columns.
- Initially, before the real instruction files were uploaded, produced a first version using its own assumptions; this was superseded and its provisional handoff file deleted (see `worklog.md`).

## Not done by the AI
- No kinetic model, fitting, or optimisation.
- No run excluded; no held-out run chosen.
- Nothing has been run on the user's machine.

## Human checks still required
- [ ] Re-run script and tests locally; compare tables.
- [ ] Confirm the uncertainty-table mapping against the original PDF.
- [ ] Check the numbers in `reports/pre_fit_observations.md` against the tables.
- [ ] Judge the hypotheses (all untested).
- [ ] Decide how to handle R3 and R7 in Level 1, and choose the held-out run before any fitting.
- [ ] Add any course-specific AI-disclosure wording.

## Level 1 – what the AI did
- Recorded the approved decisions before fitting; wrote `src/kinetics.py`, `src/fit.py`, `src/level1_summary.py`, `tests/test_model.py`; ran the fit, the R6 prediction, the sensitivities and the tests in a sandbox; generated tables, figures and `reports/level1.md`; updated the handoff files.
- Analytical choices the user should review: K_s = 1 g/L fixed; CO2 sd floor 0.10 g/L; per-level thermal multipliers with linear interpolation; bounds on parameters (notably P_max >= 108 g/L, Y_P <= 0.511); multi-start strategy; the "material change" yardstick in the sensitivity section (2 linearised SEs, which is harsh when the model misfit is large); the hand-calculated yield/sugar error split for R6; reading the user's template message as approval of my earlier proposal.
- Interpretations flagged as hypotheses only: nutrient limit on biomass, second organism in R7, temperature-dependent ethanol tolerance, run-to-run yield variation.

## Not done by the AI in Level 1
- No Level 2 or 3 work; no profile-likelihood or bootstrap intervals; no model comparison; no carbon-balance closure.
- Nothing was run on the user's machine; pytest was not run; `requirements.txt` and `README.md` were not available and were not edited.

## Human checks still required
- [ ] Re-run `src/fit.py --stage all`, `src/level1_summary.py` and `pytest -q` locally; compare tables.
- [ ] Review `reports/level1.md` numbers against the tables.
- [ ] Confirm the uncertainty-table mapping (D-03) against the original PDF.
- [ ] Judge whether the model's misfit (reduced chi-square 12.6, biomass plateau too low) is acceptable before Level 2.
- [ ] Add `scipy` to requirements; add any course-specific AI-disclosure wording.

## Level 2 – what the AI did
- Registered the candidate set, selection rule and protocols before computing; wrote `src/models.py`, `compare.py`, `uncertainty.py`, `plant_uncertainty.py`, `carbon_balance.py` and `tests/test_level2.py`; ran them in a sandbox; generated tables, figures and `reports/level2.md`; updated the handoff files.
- Analytical choices the user should review: the seven-candidate set; QAICc with c_hat from M5 (assumes independent errors, which the data violate); the 4-unit simplicity tie-break; profile threshold c_hat x 3.84; jackknife via leave-one-run-out refits (max_nfev 120); linearised-Gaussian parameter draws for plant propagation; Monte-Carlo carbon balance (n.d. uniform on [0, 0.2), t = 0 TRS and inoculum treated as measured with the brief's sds); the identifiability labelling rule (refined once after seeing results); the grouped variance decomposition; choice of four fixed plant scenarios; the linearised design criterion and the structure-separation measure; the 96 h / 34 C / 260 g/L experiment proposal; keeping K_s = 1 g/L as the documented primary value.
- Interpretations flagged as hypotheses only: lactic acid as evidence of a second organism, CO2 from biomass synthesis, non-sugar molasses carbon, nutrient limit on biomass.

## Not done by the AI in Level 2
- No Level 3 optimisation or recommendation; no experiment performed; nothing run on the user's machine; pytest not run; `requirements.txt` and `README.md` not available and not edited.

## Human checks still required
- [ ] Re-run the commands in `worklog.md` and `pytest -q` locally; compare tables.
- [ ] Review `reports/level2.md` against the tables and decide which structure(s) (M5, M2, M6) and which K_s to carry into Level 3.
- [ ] Confirm the brief's uncertainty-table mapping (D-03) and the CO2 sd floor.
- [ ] Judge whether the P_max-n ridge and the leave-out-R8 failure make M5 acceptable for 36-37 C.
- [ ] Add `scipy` to requirements; add any course-specific AI-disclosure wording.

## Level 2 packaging repair
- The AI inventoried the workspace, byte-compared preserved files, added README.md, requirements.txt, the report generators and a report-claims test, reconciled the traceability table, rebuilt the Level 2 report (one rounding wording fix) and assembled a single structured ZIP. No analysis was re-run and the frozen Level 2 selection rule and result were not changed.
- Items for the user to check: that the regenerated `data/raw/CHECKSUMS.sha256` matches your local copy (if you have one); `pytest -q` locally; the conservative version ranges in `requirements.txt`.

