param(
    [Parameter(Mandatory = $true)]
    [Alias("Input")]
    [string]$InputPath,

    [string]$WorkDir = "artifacts/math",

    [int]$Seed = 42,

    [int]$MaxPairsPerGroup = 100000,

    [int]$MaxPairsTotal = 1000000
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = (Resolve-Path (Join-Path $PSScriptRoot "..\src")).Path
$LocalPython = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$Python = if (Test-Path $LocalPython) { (Resolve-Path $LocalPython).Path } else { "python" }

$Pairs = Join-Path $WorkDir "pairs_train.csv"
$ModelDir = Join-Path $WorkDir "model"
$ValidationPredictions = Join-Path $WorkDir "predictions_validation.csv"
$ValidationReport = Join-Path $WorkDir "evaluation_validation.json"
$TestPredictions = Join-Path $WorkDir "predictions_test.csv"
$Submission = Join-Path $WorkDir "submission.csv"

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

& $Python -m bioos_benchmark.ranking.preferences `
    --input $InputPath `
    --output $Pairs `
    --split train `
    --max-pairs-per-group $MaxPairsPerGroup `
    --max-pairs-total $MaxPairsTotal `
    --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m bioos_benchmark.ranking.math_ranker train `
    --input $InputPath `
    --pairs $Pairs `
    --artifact-dir $ModelDir `
    --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m bioos_benchmark.ranking.math_ranker predict `
    --model-dir $ModelDir `
    --input $InputPath `
    --split validation `
    --output $ValidationPredictions
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m bioos_benchmark.ranking.evaluation `
    --truth $InputPath `
    --predictions $ValidationPredictions `
    --split validation `
    --output $ValidationReport `
    --seed $Seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m bioos_benchmark.ranking.math_ranker predict `
    --model-dir $ModelDir `
    --input $InputPath `
    --split test `
    --output $TestPredictions
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m bioos_benchmark.ranking.ensemble submit `
    --input $InputPath `
    --predictions $TestPredictions `
    --split test `
    --output $Submission
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Output "Math ranking pipeline completed."
Write-Output "Validation report: $ValidationReport"
Write-Output "Submission: $Submission"
