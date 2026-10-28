# Windows UTF-8 fix

Created: 2026-10-27 14:55:50. **Actual Windows execution was not performed in this Linux sandbox.**

## Root cause and fix

- On Windows, open(OUT,"w") without encoding uses the locale code page (commonly cp1252). The reports contain Unicode characters that cp1252 cannot encode.
- Original Level 1: `src/make_level1_report.py:184 open(OUT,'w').write(rep)`
- Original Level 2: `src/make_level2_report.py:329 open(OUT,'w').write(rep); print(len(rep))`
- Fixed Level 1: `src/make_level1_report.py:184 open(OUT,'w', encoding="utf-8", newline="\n").write(rep)`
- Fixed Level 2: `src/make_level2_report.py:329 open(OUT,'w', encoding="utf-8", newline="\n").write(rep); print(len(rep))`
- Six existing source files updated; 35 text `open()` calls now pass explicit encoding. The two report-equality tests were not modified or weakened.

## Non-ASCII characters

- `level1.md`: cp1252-unencodable = U+2212 (1 class).
- `level2.md`: cp1252-unencodable = U+0394, U+20B9, U+2192, U+2212, U+2248, U+2264, U+2265 (7 classes).

## Linux evidence

- Default pytest: 60 passed.
- Full pytest under cp1252 file-write simulation: 60 passed.
- Original two report-equality tests under simulation: 2 passed.
- Direct generator outputs under simulation are byte-identical to the committed reports.
- New regression test `test_report_generators_write_utf8_under_windows_cp1252_simulation` runs the same simulation with a temporary `sitecustomize.py`.

## Commands the user should run on Windows

```bat
python -m pip install -r requirements.txt
python -c "import sys,locale; print(sys.version); print(locale.getpreferredencoding(False)); print(sys.stdout.encoding)"
chcp
python -m pytest -q
python -m pytest -q tests/test_report_claims.py::test_level1_report_equals_generator_output tests/test_report_claims.py::test_level2_report_equals_generator_output -vv
python -m pytest -q tests/test_task2_consistency.py -vv
python src/make_level1_report.py "%TEMP%\fk_level1.md"
python src/make_level2_report.py "%TEMP%\fk_level2.md"
fc /B reports\level1.md "%TEMP%\fk_level1.md"
fc /B reports\level2.md "%TEMP%\fk_level2.md"
git status --short
```

Unresolved: Actual Windows pytest execution and full Windows traceback remain unverified in this Linux sandbox.

Machine-readable evidence: `windows_utf8_fix.json`, `tests/test_results.json`.
