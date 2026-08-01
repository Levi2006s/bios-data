param(
    [Parameter(Mandatory = $true)]
    [string]$DataRoot
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "src"

python -m bioos_benchmark.prepare `
    --data-root $DataRoot `
    --output data/processed/benchmark.csv `
    --max-rows-per-file 5000

python -m bioos_benchmark.train `
    --input data/processed/benchmark.csv `
    --artifact-dir artifacts/baseline

python -m bioos_benchmark.design `
    --model artifacts/baseline/model.joblib `
    --target examples/target.json `
    --output artifacts/candidates.csv `
    --count 1000

Write-Host "Demo complete. See artifacts/baseline and artifacts/candidates.csv"

