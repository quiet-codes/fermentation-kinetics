# Task 2 test and UTF-8 evidence

This is Linux sandbox execution plus a cp1252 file-encoding simulation; it is not a Windows run.

| run | command | result |
|---|---|---|
| pytest_default.log | `PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python -m pytest -q -p no:cacheprovider` | 60 passed in 4.88s |
| pytest_cp1252_sim_full.log | `PYTHONPATH=/tmp/fk-cp1252-sim PYTHONUTF8=0 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python -m pytest -q -p no:cacheprovider` | 60 passed in 4.96s |
| pytest_cp1252_sim_report_tests.log | `PYTHONPATH=/tmp/fk-cp1252-sim PYTHONUTF8=0 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python -m pytest -q -p no:cacheprovider tests/test_report_claims.py::test_level1_report_equals_generator_output tests/test_report_claims.py::test_level2_report_equals_generator_output` | 2 passed in 1.06s |

Direct generator check under simulation: `outputs/audits/task2/tests/utf8_direct_cp1252_sim.log` — both reports byte-identical.

The original report-equality tests were not weakened; explicit `encoding="utf-8", newline="\n"` was added to the generators. New regression tests are in `tests/test_task2_consistency.py`.

## Final verification after all Task 2 files were written

- `outputs/audits/task2/final_checks/final_pytest_default.log`: 60 passed in 4.81s (`PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python -m pytest -q -p no:cacheprovider`)
- `outputs/audits/task2/final_checks/final_pytest_cp1252_sim.log`: 60 passed in 4.15s (`PYTHONPATH=/tmp/fk-cp1252-sim PYTHONUTF8=0 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 /tmp/fk-audit-venv/bin/python -m pytest -q -p no:cacheprovider`)

Raw git/raw-checksum/nested-test verification: `outputs/audits/task2/final_checks/final_verification.log`. No nested `test_*.py` files or `.pyc` artifacts remain under `outputs/audits/task2/`. The only tracked modifications are the six UTF-8 source fixes; raw CSV checksums verify.
