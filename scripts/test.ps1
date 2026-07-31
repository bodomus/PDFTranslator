[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepositoryRoot = Split-Path -Parent $PSScriptRoot

Push-Location $RepositoryRoot
try {
    & uv run pytest --cov-report=term-missing
    if ($LASTEXITCODE -ne 0) {
        throw "The test suite failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
