[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $CorpusRoot,
    [string] $OutputRoot,
    [string] $ManifestPath,
    [string] $ManualResultsPath,
    [string[]] $Subset = @(),
    [switch] $DryRun,
    [switch] $FailFast,
    [string] $Pages,
    [ValidateSet("auto", "cpu", "cuda")]
    [string] $Device = "auto",
    [ValidateSet("auto", "on", "off")]
    [string] $Ocr = "auto",
    [string] $Model = "facebook/nllb-200-distilled-600M",
    [int] $BatchSize = 8,
    [int] $MaxInputTokens = 512,
    [string] $CacheDir,
    [string] $FontPath,
    [switch] $Offline,
    [switch] $Resume,
    [switch] $Overwrite
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$Arguments = @(
    "run", "python", "-m", "pdftranslate.validation",
    "--corpus-root", $CorpusRoot,
    "--device", $Device,
    "--ocr", $Ocr,
    "--model", $Model,
    "--batch-size", $BatchSize.ToString(),
    "--max-input-tokens", $MaxInputTokens.ToString()
)

if ($OutputRoot) { $Arguments += @("--output-root", $OutputRoot) }
if ($ManifestPath) { $Arguments += @("--manifest", $ManifestPath) }
if ($ManualResultsPath) { $Arguments += @("--manual-results", $ManualResultsPath) }
foreach ($SelectedSubset in $Subset) { $Arguments += @("--subset", $SelectedSubset) }
if ($DryRun) { $Arguments += "--dry-run" }
if ($FailFast) { $Arguments += "--fail-fast" }
if ($Pages) { $Arguments += @("--pages", $Pages) }
if ($CacheDir) { $Arguments += @("--cache-dir", $CacheDir) }
if ($FontPath) { $Arguments += @("--font", $FontPath) }
if ($Offline) { $Arguments += "--offline" }
if ($Resume) { $Arguments += "--resume" }
if ($Overwrite) { $Arguments += "--overwrite" }

Push-Location $RepositoryRoot
try {
    & uv @Arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
