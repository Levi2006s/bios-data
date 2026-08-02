param(
    [string]$InputPath = "data\processed\curation\curated_sample_with_splits.csv",
    [string]$LabelRegistry = "configs\label_registry.csv",
    [string]$SplitColumn = "paper_split",
    [string]$EvaluationSplit = "validation",
    [string]$WorkDir = "artifacts\math_benchmark",
    [int[]]$Seeds = @(42, 43),
    [int]$BootstrapRounds = 1000
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = (Resolve-Path (Join-Path $PSScriptRoot "..\src")).Path
$LocalPython = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$Python = if (Test-Path $LocalPython) { (Resolve-Path $LocalPython).Path } else { "python" }
$Dataset = Join-Path $WorkDir "dataset.csv"
$Pairs = Join-Path $WorkDir "pairs_train.csv"
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

& $Python -m bioos_benchmark.ranking.prepare `
    --input $InputPath --output $Dataset --split-column $SplitColumn `
    --label-registry $LabelRegistry
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m bioos_benchmark.ranking.preferences `
    --input $Dataset --output $Pairs --split train `
    --max-pairs-per-group 20000 --max-pairs-total 200000 --seed $Seeds[0]
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$PredictionFiles = @()
foreach ($Seed in $Seeds) {
    $ModelDir = Join-Path $WorkDir "model_seed$Seed"
    $Predictions = Join-Path $WorkDir "predictions_${EvaluationSplit}_seed$Seed.csv"
    $Evaluation = Join-Path $WorkDir "evaluation_${EvaluationSplit}_seed$Seed.json"
    & $Python -m bioos_benchmark.ranking.math_ranker train `
        --input $Dataset --pairs $Pairs --artifact-dir $ModelDir --seed $Seed
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m bioos_benchmark.ranking.math_ranker predict `
        --model-dir $ModelDir --input $Dataset --split $EvaluationSplit --output $Predictions
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m bioos_benchmark.ranking.evaluation `
        --truth $Dataset --predictions $Predictions --split $EvaluationSplit `
        --output $Evaluation --bootstrap-rounds $BootstrapRounds --seed $Seed
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $PredictionFiles += $Predictions
}

if ($PredictionFiles.Count -ge 2) {
    $Ensemble = Join-Path $WorkDir "ensemble_${EvaluationSplit}.csv"
    $EnsembleEvaluation = Join-Path $WorkDir "evaluation_ensemble_${EvaluationSplit}.json"
    $EqualWeights = @(1..$PredictionFiles.Count | ForEach-Object { 1.0 })
    & $Python -m bioos_benchmark.ranking.ensemble ensemble `
        --inputs $PredictionFiles --weights $EqualWeights --group-field target_id --output $Ensemble
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m bioos_benchmark.ranking.evaluation `
        --truth $Dataset --predictions $Ensemble --split $EvaluationSplit `
        --output $EnsembleEvaluation --bootstrap-rounds $BootstrapRounds --seed 44
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $AuditPredictions = $Ensemble
} else {
    $AuditPredictions = $PredictionFiles[0]
}

& $Python -m bioos_benchmark.ranking.leakage `
    --truth $Dataset --predictions $AuditPredictions --evaluation-split $EvaluationSplit `
    --output (Join-Path $WorkDir "shortcut_audit_${EvaluationSplit}.json")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Output "Mathematical benchmark completed: $WorkDir"
