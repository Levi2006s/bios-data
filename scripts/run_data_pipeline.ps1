param(
    [Parameter(Mandatory = $true)]
    [string]$DataRoot,
    [int]$MaxRowsPerFile = 5000
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "src"

python -m bioos_benchmark.audit `
    --data-root $DataRoot `
    --output data/processed/audit.csv `
    --hash-inputs

python -m bioos_benchmark.prepare `
    --data-root $DataRoot `
    --output data/processed/benchmark.csv `
    --max-rows-per-file $MaxRowsPerFile `
    --direction-overrides configs/direction_overrides.csv

python -m bioos_benchmark.split `
    --input data/processed/benchmark.csv `
    --output data/processed/benchmark_with_split.csv

python -m bioos_benchmark.validate `
    --input data/processed/benchmark_with_split.csv `
    --report data/processed/validation_report.json

Write-Host "Data pipeline completed: data/processed"

