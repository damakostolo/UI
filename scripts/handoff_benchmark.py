#!/usr/bin/env python3
"""Measure actual local inference and in-process health latency; no volunteer data."""
from __future__ import annotations

import csv
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.features import MODEL_FEATURES  # noqa: E402

OUT = ROOT / "thesis_handoff/05_tests"
OUT.mkdir(parents=True, exist_ok=True)


def measure(operation, repeats=30, warmup=5):
    for _ in range(warmup):
        operation()
    measurements = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        operation()
        measurements.append((time.perf_counter_ns() - start) / 1_000_000)
    return measurements


def main():
    split = json.loads((ROOT / "results/split_manifest.json").read_text(encoding="utf-8"))
    if split.get("source") != "synthetic" or split.get("is_synthetic") is not True:
        raise ValueError("Benchmark requires synthetic split")
    frame = pd.read_csv(ROOT / "data/sample_synthetic/feature_rows.csv")
    test = frame[frame.participant_id.isin(split["test_ids"])][list(MODEL_FEATURES)]
    artifact = joblib.load(ROOT / "results/synthetic/demo_model.joblib")
    if artifact.get("source") != "synthetic":
        raise ValueError("Model provenance is not synthetic")
    model = artifact["pipeline"]
    inference = measure(lambda: model.predict_proba(test))
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    from fastapi.testclient import TestClient  # noqa: E402
    from backend.app import app  # noqa: E402
    with TestClient(app) as client:
        health = measure(lambda: client.get("/api/v1/health"))
    when = datetime.now(timezone.utc).isoformat()
    rows = []
    for name, samples, source, synthetic, count, method in (
        ("logistic_regression_predict_proba", inference, "synthetic", "true", len(test), "30 batched local predictions after 5 warmups"),
        ("GET_health_TestClient", health, "derived", "false", 1, "30 in-process FastAPI TestClient requests after 5 warmups"),
    ):
        rows.append({"operation": name, "source_kind": source, "is_synthetic": synthetic,
                     "rows_per_iteration": count, "warmup": 5, "repetitions": 30,
                     "p50_ms_per_iteration": float(np.percentile(samples, 50)),
                     "p95_ms_per_iteration": float(np.percentile(samples, 95)),
                     "p50_ms_per_row": float(np.percentile(samples, 50)) / count,
                     "p95_ms_per_row": float(np.percentile(samples, 95)) / count,
                     "measured_at_utc": when, "method": method})
    with (OUT / "performance_benchmarks.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    (OUT / "performance_environment.json").write_text(json.dumps({"measured_at_utc": when, "os": platform.platform(),
        "python": platform.python_version(), "cpu": platform.processor(), "logical_cpus": os.cpu_count(),
        "model_source": "synthetic", "test_rows": len(test)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
