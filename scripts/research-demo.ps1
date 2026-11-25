$ErrorActionPreference = 'Stop'
python scripts/generate_synthetic_data.py --seed 20261103 --output data/sample_synthetic
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m ml.research --input data/sample_synthetic/feature_rows.csv --output results/synthetic
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python scripts/finalize_results.py
exit $LASTEXITCODE
