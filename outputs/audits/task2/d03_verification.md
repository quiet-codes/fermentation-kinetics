# D-03 verification against the available brief

Created: 2026-10-27 14:55:50. **Original assignment PDF is unavailable.**

## Decision and source

- `handoff/DECISIONS.md line 7`: D-03: Uncertainty table read in row order (biomass, TRS, ethanol, CO2, by-products, pH).
- Available source: `docs/assignment_brief.md` (PDF-extracted text).

## What was verified

- All six uncertainty strings quoted in the extracted brief are present.
- The implemented row-order mapping is present in the source and consistent across the stages.
- Fitting/frozen records use the documented 0.10 g/L CO2 floor; Phase 0/carbon balance do not.

| species | implemented one-sd rule |
|---|---|
| biomass | `0.035*measured + 0.08 g/L` |
| TRS | `0.01*measured + 0.4 g/L` |
| ethanol | `0.012*measured + 0.25 g/L` |
| CO2_fitting | `0.02*measured + 0.10 g/L floor` |
| CO2_phase0_and_carbon_balance | `0.02*measured (no floor)` |
| glycerol_and_detected_lactic | `0.03*measured` |
| pH | `absolute 0.04` |

## What cannot be definitively verified without the original PDF

- Row alignment of the PDF-extracted uncertainty table (the table is unlabelled in the brief).
- Exact meaning of "about ±2%" for CO2 and "about ±3%" for by-products (whether additive floors, absolute errors, or different conventions were intended).
- Whether the original PDF contained additional requirements, caveats, or units omitted by extraction.

No missing requirement was invented. The approximate "about ±2%" / "about ±3%" wording was not converted into an exact formula beyond the documented implementation.

Machine-readable evidence: `d03_verification.json`. New regression test: `tests/test_task2_consistency.py::test_d03_uncertainty_mapping_documented_and_implemented_consistently`.
