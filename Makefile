.PHONY: research-demo research-real test
research-demo:
	python scripts/generate_synthetic_data.py --seed 20261103 --output data/sample_synthetic
	python -m ml.research --input data/sample_synthetic/feature_rows.csv --output results/synthetic
	python scripts/finalize_results.py
research-real:
	python scripts/research_real.py
test:
	python -m pytest -q
	cd frontend && npm run typecheck && npm test
