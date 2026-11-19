[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Uv {
    param(
        [Parameter(Mandatory)]
        [string[]] $Arguments
    )

    & uv @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "uv $($Arguments -join ' ') failed with exit code $LASTEXITCODE."
    }
}

$RepositoryRoot = Split-Path -Parent $PSScriptRoot

Push-Location $RepositoryRoot
try {
    Invoke-Uv -Arguments @("run", "ruff", "format", "--check", ".")
    Invoke-Uv -Arguments @("run", "ruff", "check", ".")
    Invoke-Uv -Arguments @("run", "mypy", "src")
    Invoke-Uv -Arguments @("run", "pytest")
}
finally {
    Pop-Location
}
