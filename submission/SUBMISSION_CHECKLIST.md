# Submission checklist

## Deliverables present

- [x] Level 1 report `level1/level1.md`
- [x] Level 2 report `level2/level2.md`
- [x] Level 3 report `level3/level3.md`
- [x] Phase 0 observations `phase0/pre_fit_observations.md`
- [x] Code that reproduces every number: `source/src/`
- [x] Tests: `source/tests/` (optimisation constraints, completion rule, economics, 36 C scenario,
      unfinished-batch handling, encoding/formatting, report claims)
- [x] Raw data and checksums: `data/raw/`
- [x] Work log `worklog.md` and AI-use note `AI_USE.md`
- [x] Requirements traceability `requirements_traceability.csv`
- [x] Manifest with SHA-256 for every file: `manifest.csv`, `CHECKSUMS.sha256`

## Verification performed (Linux sandbox)

- [x] Full test suite passes
- [x] Level 3 workflow executes end to end
- [x] Consistency audit passes (report vs tables vs frozen records)
- [x] Frozen Level 2 selection unchanged (M5, D-24, R6 never used for tuning)
- [x] All eight carbon balances present
- [x] Raw CSV checksums verify
- [x] Generated CSV/JSON are ASCII with LF endings
- [x] Every figure referenced by the reports exists
- [x] ZIP integrity checked and archive listing inspected

## Outstanding - to be done by the student

- [ ] Run `python -m pytest -q` on Windows and record the result
- [ ] Run `.\scripts\reproduce_level3.ps1` on Windows
- [ ] Complete the editable personal-contribution section in `AI_USE.md`
- [ ] Confirm any PDF-only assignment requirement that is not in `assignment/assignment_brief.md`
- [ ] Check the report renders correctly in the viewer/markdown tool of choice
