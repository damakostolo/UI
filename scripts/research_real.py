#!/usr/bin/env python3
"""Real-data route. Never creates observations when no authorized bundle exists."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.import_real_data import import_bundle  # noqa: E402
from ml.research import evaluate  # noqa: E402


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--bundle", type=Path)
    args = parser.parse_args(); output = ROOT / "results/real"; output.mkdir(parents=True, exist_ok=True)
    if not args.bundle:
        (output / "README.md").write_text("# Реальних даних немає\n\nПогодьте процедуру за `docs/EXPERIMENT_PROTOCOL.md`, зберіть явні згоди, події та окремі мітки переваги. Створіть `manifest.json` із `source=volunteer`, `is_synthetic=false`, `consent_document_version`, `consent_approved_by`, `collection_procedure` і масивом `consents` (participant_id, consented_at, consent_version, scope=research). Додайте `events.jsonl`, `preference_labels.csv`; за наявності UX-досліду `ux_trials.csv`. Запустіть `python scripts/research_real.py --bundle ШЛЯХ`. Ніяких реальних результатів поки не обчислено.\n", encoding="utf-8")
        print("MODEL_NOT_EVALUABLE: no real volunteer bundle supplied")
        return 0
    staging = ROOT / "data/real"
    counts = import_bundle(args.bundle, staging)
    try:
        evaluate(staging / "feature_rows.csv", output, ROOT, "volunteer")
        print(json.dumps(counts))
    except ValueError as exc:
        (output / "MODEL_NOT_EVALUABLE.md").write_text(f"# MODEL_NOT_EVALUABLE\n\n{exc}\n", encoding="utf-8")
        print(f"MODEL_NOT_EVALUABLE: {exc}")
    trials = staging / "ux_trials.csv"
    if trials.exists():
        import pandas as pd
        frame = pd.read_csv(trials)
        if not frame.empty:
            summary = frame.groupby("condition", sort=True).agg(participants=("participant_id", "nunique"), trials=("trial_id", "count"),
                median_elapsed_ms=("elapsed_ms", "median"), q1_elapsed_ms=("elapsed_ms", lambda s: s.quantile(.25)),
                q3_elapsed_ms=("elapsed_ms", lambda s: s.quantile(.75)), median_clicks=("click_count", "median"),
                success_rate=("completed", "mean")).reset_index()
            frame.to_csv(output / "ux_trials.csv", index=False); summary.to_csv(output / "ux_summary.csv", index=False)
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(8,5), dpi=200); ax.bar(summary.condition, summary.median_elapsed_ms)
            ax.set_ylabel("Медіана часу, мс"); ax.set_title("Реальні добровільні UX-спроби")
            fig.tight_layout(); fig.savefig(output / "ux_comparison.png"); fig.savefig(output / "ux_comparison.svg"); plt.close(fig)
    return 0


if __name__ == "__main__": raise SystemExit(main())
