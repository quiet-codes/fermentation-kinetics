<#
    Reproduce the whole Level 3 workflow on Windows (PowerShell 5.1 or 7+).

    Usage, from the project root:

        .\scripts\reproduce_level3.ps1

    Optional: pass a Python executable, e.g.
        .\scripts\reproduce_level3.ps1 -Python "C:\Python312\python.exe"

    The script stops at the first failing stage (no silent continuation), because each later
    stage consumes the outputs of the earlier ones.  Nothing here weakens a test or rewrites
    raw data: the raw CSVs are only verified against data\raw\CHECKSUMS.sha256.

    Windows-specific notes
    ----------------------
    * Generated CSV/JSON files are written with explicit UTF-8 and LF line endings by the
      source code, so they are byte-identical to the Linux run regardless of the Windows
      default line terminator.  This was the cause of a previously reported local failure
      ("data_quality.csv contains CRLF") and is now pinned in every writer.
    * The report-comparison checks use a byte comparison; run this script first, then
      `git status --short` to see whether anything changed.
#>
[CmdletBinding()]
param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

function Invoke-Stage {
    param([string]$Label, [scriptblock]$Action)
    Write-Host ""
    Write-Host "== $Label ==" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "stage failed: $Label (exit code $LASTEXITCODE)"
    }
}

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Write-Host "project root: $root"

Invoke-Stage "environment" {
    & $Python -c "import platform,sys;print('python',sys.version.split()[0],'|',platform.platform())"
    & $Python -c "import numpy,scipy,pandas,matplotlib;print('numpy',numpy.__version__,'scipy',scipy.__version__,'pandas',pandas.__version__,'matplotlib',matplotlib.__version__)"
    Write-Host "file-write default encoding:"
    & $Python -c "import locale;print(locale.getpreferredencoding(False))"
}

Invoke-Stage "raw-data checksums" {
    Push-Location "data\raw"
    try {
        Get-Content "CHECKSUMS.sha256" | ForEach-Object {
            if ($_ -match '^\s*$') { return }
            $parts = $_ -split '\s+', 2
            $expected = $parts[0]
            $name = $parts[1].Trim()
            $actual = (Get-FileHash -Algorithm SHA256 -Path $name).Hash.ToLower()
            if ($actual -ne $expected.ToLower()) {
                throw "raw checksum mismatch for $name"
            }
            Write-Host "OK  $name"
        }
    }
    finally {
        Pop-Location
    }
}

Invoke-Stage "Level 3 workflow" {
    & $Python "src\level3_optimize.py" --stage all --n-draws 200
}

Invoke-Stage "report generation" {
    & $Python "src\make_level3_report.py"
}

Invoke-Stage "consistency audit" {
    & $Python "src\level3_consistency_audit.py"
}

Invoke-Stage "full test suite" {
    & $Python -m pytest -q
}

Invoke-Stage "submission snapshot" {
    & $Python "scripts\build_submission.py"
    if ($LASTEXITCODE -ne 0) { throw "build_submission.py failed" }
    & $Python "scripts\verify_submission.py"
}

Invoke-Stage "final archive" {
    & $Python "scripts\create_final_zip.py"
}

Write-Host ""
Write-Host "Level 3 reproduction complete." -ForegroundColor Green
Write-Host "Next: 'git status --short' to see whether any generated file differs from the committed copy."
