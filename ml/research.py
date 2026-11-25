from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import importlib.metadata
import time
from collections import Counter
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .features import FEATURES_CAT, FEATURES_NUM, LAYOUTS, MODEL_FEATURES, validate_predecision
from .policy import PolicyConfig, decide, rule_layout

SEED = 20261103
WARNING = "СИНТЕТИЧНІ ДАНІ — НЕ Є ОЦІНКОЮ РЕАЛЬНИХ КОРИСТУВАЧІВ"


def save_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def save_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def split_participants(frame: pd.DataFrame, seed: int = SEED) -> dict[str, list[str]]:
    ids = np.array(sorted(frame.participant_id.unique()))
    np.random.default_rng(seed).shuffle(ids)
    n = len(ids)
    if n < 15:
        raise ValueError("MODEL_NOT_EVALUABLE: fewer than 15 participant groups")
    a, b = round(n * .6), round(n * .8)
    split = {"train_ids": ids[:a].tolist(), "validation_ids": ids[a:b].tolist(), "test_ids": ids[b:].tolist()}
    if any(set(split[x]) & set(split[y]) for x, y in (("train_ids", "validation_ids"), ("train_ids", "test_ids"), ("validation_ids", "test_ids"))):
        raise AssertionError("Participant overlap")
    for ids_ in split.values():
        if set(frame.loc[frame.participant_id.isin(ids_), "preferred_layout"]) != set(LAYOUTS):
            raise ValueError("MODEL_NOT_EVALUABLE: missing class in participant split")
    return split


def pipeline(kind: str, variant: int) -> Pipeline:
    numeric = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
    categorical = Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False))])
    pre = ColumnTransformer([("numeric", numeric, list(FEATURES_NUM)), ("categorical", categorical, list(FEATURES_CAT))])
    if kind == "logistic_regression":
        model = LogisticRegression(C=[.3, 1.0][variant], max_iter=500, random_state=SEED)
    elif kind == "random_forest":
        model = RandomForestClassifier(n_estimators=[80, 120][variant], max_depth=[5, 8][variant], random_state=SEED, n_jobs=1)
    elif kind == "xgboost":
        from xgboost import XGBClassifier
        model = XGBClassifier(n_estimators=[80, 120][variant], max_depth=[3, 4][variant], learning_rate=.08,
                              objective="multi:softprob", num_class=3, random_state=SEED, n_jobs=1, eval_metric="mlogloss")
    else:
        raise ValueError(kind)
    return Pipeline([("preprocess", pre), ("model", model)])


def score(y_true, y_pred, proba=None) -> dict:
    precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, labels=LAYOUTS, average="macro", zero_division=0)
    out = {"accuracy": float(accuracy_score(y_true, y_pred)), "macro_precision": float(precision),
           "macro_recall": float(recall), "macro_f1": float(f1)}
    if proba is not None:
        # Probability columns are explicitly ordered as LAYOUTS, unlike sklearn's
        # lexicographic label ordering. Index directly to avoid a silent mismatch.
        indices = [LAYOUTS.index(label) for label in y_true]
        out["logloss"] = float(-np.log(np.clip(proba[np.arange(len(indices)), indices], 1e-15, 1)).mean())
    return out


def chart(path: Path, labels: list[str], values: list[float], ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 5), dpi=200)
    ax.bar(labels, values, color="#2563a6")
    ax.set_ylabel(ylabel); ax.tick_params(axis="x", rotation=20)
    if "synthetic" in path.parts:
        fig.text(.5, .01, WARNING, ha="center", fontsize=9, color="darkred", weight="bold")
    fig.tight_layout(rect=(0, .05, 1, 1))
    fig.savefig(path); fig.savefig(path.with_suffix(".svg")); plt.close(fig)


def evaluate(input_csv: Path, output: Path, root: Path, source: str = "synthetic") -> dict:
    output.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(input_csv)
    expected_flag = source == "synthetic"
    if not all(frame.source == source) or not all(frame.is_synthetic == expected_flag):
        raise ValueError("Mixed or mislabeled data source")
    if source == "volunteer" and not all(frame.label_source == "explicit_preference"):
        raise ValueError("Real labels must be explicit preferences")
    for row in frame.to_dict("records"):
        validate_predecision(row)
    if frame.duplicated(["participant_id", "session_id", "decision_at"]).any():
        raise ValueError("Duplicate preference decisions")
    split = split_participants(frame)
    groups = {name: frame[frame.participant_id.isin(ids)].copy() for name, ids in split.items()}
    train, valid, test = (groups[k] for k in ("train_ids", "validation_ids", "test_ids"))
    split_info = {**split, "seed": SEED, "source": source, "is_synthetic": expected_flag, "disjoint": True, "class_counts": {k: v.preferred_layout.value_counts().to_dict() for k, v in groups.items()},
                  "cutoffs": "Each observed_until < decision_at; all model inputs are predecision aggregates"}
    save_json(root / ("results/split_manifest.json" if expected_flag else "results/real/split_manifest.json"), split_info)
    comparison, matrices = [], {}
    for name in ("static", "rule", "logistic_regression", "random_forest", "xgboost"):
        if name == "static":
            pred = np.repeat("standard", len(test)); prob = None; fit_choice = "fixed"
        elif name == "rule":
            pred = np.array([rule_layout(r) for r in test.to_dict("records")]); prob = None; fit_choice = "fixed"
        else:
            try:
                candidates = []
                for variant in (0, 1):
                    fitted = pipeline(name, variant)
                    if name == "xgboost":
                        fitted.fit(train[list(MODEL_FEATURES)], pd.Categorical(train.preferred_layout, categories=LAYOUTS).codes)
                        valid_pred = np.array(LAYOUTS)[fitted.predict(valid[list(MODEL_FEATURES)]).astype(int)]
                    else:
                        fitted.fit(train[list(MODEL_FEATURES)], train.preferred_layout)
                        valid_pred = fitted.predict(valid[list(MODEL_FEATURES)])
                    candidates.append((score(valid.preferred_layout, valid_pred)["macro_f1"], variant, fitted))
                _, fit_choice, fitted = max(candidates, key=lambda t: (t[0], -t[1]))
                start = time.perf_counter()
                raw = fitted.predict(test[list(MODEL_FEATURES)])
                prob_raw = fitted.predict_proba(test[list(MODEL_FEATURES)])
                latency = 1000 * (time.perf_counter() - start) / len(test)
                classes = np.array(LAYOUTS) if name == "xgboost" else fitted.named_steps["model"].classes_
                pred = np.array(LAYOUTS)[raw.astype(int)] if name == "xgboost" else raw
                prob = np.column_stack([prob_raw[:, list(classes).index(c)] for c in LAYOUTS])
                if name == "logistic_regression":
                    joblib.dump({"pipeline": fitted, "classes": list(LAYOUTS), "source": source}, output / "demo_model.joblib" if source == "synthetic" else output / "model.joblib")
            except ImportError:
                comparison.append({"model": name, "status": "BLOCKED_XGBOOST_UNAVAILABLE", "accuracy": "", "macro_precision": "", "macro_recall": "", "macro_f1": "", "logloss": "", "coverage": "", "latency_ms_per_row": "", "source": source, "is_synthetic": str(expected_flag).lower(), "selected_variant": ""})
                continue
        metrics = score(test.preferred_layout, pred, prob)
        cm = confusion_matrix(test.preferred_layout, pred, labels=LAYOUTS)
        matrices[name] = cm.tolist()
        comparison.append({"model": name, "status": "PASS", **metrics, "logloss": metrics.get("logloss", ""), "coverage": 1.0,
                           "latency_ms_per_row": latency if name not in ("static", "rule") else "", "source": source,
                           "is_synthetic": str(expected_flag).lower(), "selected_variant": fit_choice})
    save_csv(output / "models_comparison.csv", comparison)
    save_json(output / "evaluation_report.json", {"source": source, "is_synthetic": expected_flag, "test_rows": len(test), "confusion_matrices": matrices,
                                                   "metric_note": "Offline preference prediction; not UX improvement"})
    counts = frame.preferred_layout.value_counts().reindex(LAYOUTS, fill_value=0)
    save_json(output / "dataset_summary.json", {"source": source, "is_synthetic": expected_flag, "n_participants": frame.participant_id.nunique(),
                                                   "n_rows": len(frame), "class_counts": counts.to_dict(), "warning": WARNING if expected_flag else ""})
    (output / "dataset_card.md").write_text(f"# Набір даних\n\nДжерело: **{source}**. Рядків: {len(frame)}; псевдонімних учасників: {frame.participant_id.nunique()}.\n\n{WARNING if expected_flag else 'Мітки — явні добровільні переваги.'}\n\nЦіль: preferred_layout; метрики стосуються прогнозу переваги, не UX.\n", encoding="utf-8")
    (output / "model_card.md").write_text(
        f"# Картка моделей\n\nДжерело: **{source}**; is_synthetic={str(expected_flag).lower()}.\n\n"
        "Призначення: офлайнове передбачення явно зазначеного бажаного макета. Не передбачає час виконання завдань. "
        "Усі моделі отримують однаковий набір predecision ознак із `results/feature_dictionary.csv`. "
        "Підбір двох варіантів параметрів на validation, одноразова оцінка на test, групи учасників не перетинаються. "
        "Статичний і правиловий baseline не мають каліброваних імовірностей. "
        "Застосування до реальних людей потребує окремих добровільних міток, перевірки класів, калібрування й UX-досліду.\n\n"
        + (WARNING if expected_flag else "Реальні дані вимагають незалежного аналізу обмежень.") + "\n", encoding="utf-8")
    save_json(output / "environment.json", {"python": platform.python_version(), "system": platform.platform(),
                                             "packages": {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "scikit-learn", "matplotlib", "xgboost")},
                                             "source": source, "is_synthetic": expected_flag})
    if expected_flag:
        feature_summary = [{"feature": key, "mean": float(frame[key].mean()), "median": float(frame[key].median()),
                            "source": "synthetic", "is_synthetic": "true"} for key in FEATURES_NUM]
        save_csv(output / "feature_summary.csv", feature_summary)
        fig, axes = plt.subplots(1, 3, figsize=(12, 4), dpi=200)
        for ax, key, title in zip(axes, ("opens_tasks_7d", "opens_reports_7d", "quick_actions_7d"),
                                  ("Завдання", "Звіти", "Швидкі дії")):
            ax.hist(frame[key], bins=12, color="#2563a6"); ax.set_title(title); ax.set_xlabel("Кількість за 7 діб")
        axes[0].set_ylabel("Кількість рядків")
        fig.text(.5, .01, WARNING, ha="center", fontsize=8, color="darkred", weight="bold")
        fig.tight_layout(rect=(0, .06, 1, 1)); fig.savefig(output / "feature_distribution.png"); fig.savefig(output / "feature_distribution.svg"); plt.close(fig)
        chart(output / "class_distribution.png", list(LAYOUTS), counts.tolist(), "Кількість синтетичних рядків")
        chart(output / "models_comparison.png", [r["model"] for r in comparison if r["status"] == "PASS"],
              [float(r["macro_f1"]) for r in comparison if r["status"] == "PASS"], "Macro-F1")
        best = max((r for r in comparison if r["status"] == "PASS" and r["model"] not in ("static", "rule")), key=lambda r: float(r["macro_f1"]))
        for model_name, values in matrices.items():
            cm = np.array(values); fig, ax = plt.subplots(figsize=(7, 6), dpi=200); ax.imshow(cm, cmap="Blues")
            ax.set_xticks(range(3), LAYOUTS); ax.set_yticks(range(3), LAYOUTS); ax.set_xlabel("Прогноз"); ax.set_ylabel("Явна перевага")
            ax.set_title(model_name)
            for i in range(3):
                for j in range(3): ax.text(j, i, str(cm[i, j]), ha="center", va="center")
            fig.text(.5, .01, WARNING, ha="center", fontsize=8, color="darkred", weight="bold"); fig.tight_layout(rect=(0, .05, 1, 1))
            for name in (f"confusion_matrix_{model_name}", "confusion_matrix" if model_name == best["model"] else None):
                if name:
                    fig.savefig(output / f"{name}.png"); fig.savefig(output / f"{name}.svg")
            plt.close(fig)
        # Policy replay is a technical ablation, never an estimate of UX benefit.
        model_data = joblib.load(output / "demo_model.joblib")
        model = model_data["pipeline"]
        probabilities = model.predict_proba(test[list(MODEL_FEATURES)])
        ablation = []
        for stage in ("ML", "ML+threshold", "ML+threshold+stability+user_control"):
            offered = changed = fallback = 0
            for row, p in zip(test.to_dict("records"), probabilities):
                probs = dict(zip(model.named_steps["model"].classes_, p))
                if stage == "ML":
                    proposal = max(probs, key=probs.get); decision = proposal != row["current_layout"]
                else:
                    config = PolicyConfig(min_events=5 if stage.endswith("user_control") else 0, cooldown_hours=24 if stage.endswith("user_control") else 0)
                    policy = decide(probs, row["current_layout"], sum(int(row[k]) for k in ("opens_tasks_7d", "opens_reports_7d", "quick_actions_7d")), config=config)
                    decision = policy["decision"] == "propose"
                    proposal = policy["proposed_layout"]
                offered += decision; changed += decision and stage != "ML+threshold+stability+user_control"
                fallback += not decision
            ablation.append({"stage": stage, "recommendations": offered, "automatic_changes": changed, "fallback": fallback,
                             "coverage": offered / len(test), "source": "synthetic", "is_synthetic": "true"})
        save_csv(output / "ablation.csv", ablation)
        save_csv(output / "policy_metrics.csv", ablation)
        chart(output / "ablation.png", [r["stage"] for r in ablation], [r["coverage"] for r in ablation], "Частка пропозицій")
        save_json(output / "system_benchmark.json", {"source": "synthetic", "is_synthetic": True,
                                                          "latency_ms_per_row_observed": {r["model"]: r["latency_ms_per_row"] for r in comparison if r["status"] == "PASS"},
                                                          "note": "Latency depends on host; no UX latency claim"})
    save_json(root / ("results/config_snapshot.json" if expected_flag else "results/real/config_snapshot.json"), {"seed": SEED, "source": source, "is_synthetic": expected_flag,
                                                     "input_sha256": hashlib.sha256(input_csv.read_bytes()).hexdigest(), "python": platform.python_version(),
                                                     "sklearn": sklearn.__version__, "pandas": pd.__version__,
                                                     "xgboost": importlib.metadata.version("xgboost"),
                                                     "policy": PolicyConfig().__dict__,
                                                     "models": "two validation candidates each; one held-out test pass"})
    return {"rows": len(frame), "comparison": comparison}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--input", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", choices=["synthetic", "volunteer"], default="synthetic")
    args = parser.parse_args(); evaluate(args.input, args.output, Path(__file__).resolve().parents[1], args.source)
