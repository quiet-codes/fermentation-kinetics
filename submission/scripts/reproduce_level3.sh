#!/usr/bin/env bash
# Reproduce the whole Level 3 workflow on Linux/macOS.
#
#   bash scripts/reproduce_level3.sh
#
# Assumes the dependencies in requirements.txt are installed in the active interpreter.
# Every stage writes its own outputs; a failure stops the run so that dependent products are
# not silently presented as reproduced.
set -euo pipefail

PY="${PYTHON:-python}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== environment =="
"$PY" - <<'PY'
import platform, sys
print("python", sys.version.split()[0], "|", platform.platform())
try:
    import numpy, scipy, pandas, matplotlib
    print("numpy", numpy.__version__, "scipy", scipy.__version__,
          "pandas", pandas.__version__, "matplotlib", matplotlib.__version__)
except Exception as exc:            # noqa: BLE001
    print("dependency check failed:", exc)
    raise
PY

echo "== raw-data checksums =="
(cd data/raw && sha256sum -c CHECKSUMS.sha256)

echo "== Level 3 workflow (input audit, grid, recommendations, uncertainty, comparison, figures, answers) =="
"$PY" src/level3_optimize.py --stage all --n-draws 200

echo "== report =="
"$PY" src/make_level3_report.py

echo "== consistency audit =="
"$PY" src/level3_consistency_audit.py

echo "== tests =="
"$PY" -m pytest -q

echo "== submission snapshot =="
"$PY" scripts/build_submission.py
"$PY" scripts/verify_submission.py

echo "== archive =="
"$PY" scripts/create_final_zip.py

echo "Level 3 reproduction complete."
