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

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found. Install uv and ensure it is available on PATH."
}

Push-Location $RepositoryRoot
try {
    Invoke-Uv -Arguments @("python", "find", "3.12")
    Invoke-Uv -Arguments @("sync", "--frozen", "--all-groups")
    Invoke-Uv -Arguments @("run", "pre-commit", "install", "--install-hooks")
    Invoke-Uv -Arguments @("run", "pdftranslate", "--version")
}
finally {
    Pop-Location
}
