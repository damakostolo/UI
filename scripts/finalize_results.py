#!/usr/bin/env python3
"""Build thesis handoff files from actual artifacts, never invent measurements."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def read_csv(path: Path):
    with path.open(encoding="utf-8", newline="") as f: return list(csv.DictReader(f))


def write(path: Path, text: str): path.write_text(text, encoding="utf-8")


def finalize():
    summary = json.loads((RESULTS / "synthetic/dataset_summary.json").read_text(encoding="utf-8"))
    comparison = read_csv(RESULTS / "synthetic/models_comparison.csv")
    ablation = read_csv(RESULTS / "synthetic/ablation.csv")
    feature_rows = [
        ("opens_tasks_7d", "Відкриття завдань за 7 діб", "кількість", "до рішення", "0"),
        ("opens_reports_7d", "Відкриття звітів за 7 діб", "кількість", "до рішення", "0"),
        ("quick_actions_7d", "Швидкі дії за 7 діб", "кількість", "до рішення", "0"),
        ("avg_actions_per_session_7d", "Середня кількість дозволених дій на сесію", "дії/сесія", "до рішення", "0"),
        ("active_sessions_7d", "Кількість сесій за 7 діб", "кількість", "до рішення", "0"),
        ("prior_undo_rate", "Частка попередніх скасувань змін", "частка", "до рішення", "0"),
        ("last_device_category", "Категорія пристрою", "категорія", "до рішення", "unknown"),
        ("last_viewport_category", "Категорія ширини екрана", "категорія", "до рішення", "unknown"),
        ("time_of_day_bin", "Частина доби", "категорія", "момент рішення", "unknown"),
        ("current_layout", "Поточний макет", "категорія", "момент рішення", "standard"),
    ]
    with (RESULTS / "feature_dictionary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f); writer.writerow(("feature", "definition", "unit", "available_at", "missing_policy")); writer.writerows(feature_rows)
    rows = ["# Таблиці для розділу 2", "", "**Усі наведені числові значення — синтетична перевірка коду, не оцінка реальних людей.**", "", "## Таблиця 2.1 — допустимі макети", "", "| Макет | Характеристика |", "|---|---|", "| standard | Звичайний порядок і щільність |", "| compact | Компактні картки, швидкі дії першими |", "| focus | Велика зона завдань |", "", "## Таблиця 2.2 — ознаки", "", "Джерело: [словник ознак](feature_dictionary.csv).", "", "## Таблиця 2.3 — набір даних", "", f"Синтетичних псевдонімних учасників: {summary['n_participants']}; рядків: {summary['n_rows']}.", "", "| Клас | Рядки |", "|---|---:|"]
    rows.extend(f"| {k} | {v} |" for k, v in summary["class_counts"].items())
    rows += ["", "## Таблиця 2.4 — offline порівняння прогнозу переваги", "", "| Модель | Accuracy | Macro-F1 | LogLoss | Статус |", "|---|---:|---:|---:|---|"]
    rows.extend(f"| {r['model']} | {r['accuracy']} | {r['macro_f1']} | {r['logloss']} | {r['status']} |" for r in comparison)
    rows += ["", "## Таблиця 2.5 — технічна абляція політики", "", "| Стадія | Пропозиції | Fallback | Coverage |", "|---|---:|---:|---:|"]
    rows.extend(f"| {r['stage']} | {r['recommendations']} | {r['fallback']} | {r['coverage']} |" for r in ablation)
    rows += ["", "## Таблиця 2.6 — ризики і обмеження", "", "Джерело: [обмеження](LIMITATIONS_UA.md). Реальний UX-ефект невідомий.", ""]
    write(RESULTS / "THESIS_TABLES_UA.md", "\n".join(rows))
    figures = ["# Рисунки для розділу 2", "", "**СИНТЕТИЧНІ ДАНІ — НЕ Є ОЦІНКОЮ РЕАЛЬНИХ КОРИСТУВАЧІВ.**", ""]
    for name, caption in (("class_distribution", "Розподіл синтетичних міток; вісь Y — кількість рядків."),
                          ("feature_distribution", "Розподіл трьох числових ознак за синтетичними рядками."),
                          ("models_comparison", "Порівняння Macro-F1 на синтетичному test split."),
                          ("confusion_matrix", "Матриця помилок прогнозу переваги; рядки — мітка, стовпці — прогноз."),
                          ("ablation", "Частка пропозицій для трьох варіантів політики.")):
        figures.append(f"- Рисунок: {caption} [PNG](synthetic/{name}.png), [SVG](synthetic/{name}.svg).")
    figures += ["", "## Діаграми архітектури й методу", "", "Джерела Mermaid та експортовані SVG/PNG: `docs/diagrams/` (`erd`, `component`, `system_context`, `use_cases`, `sequence_recommendation`, `activity_hybrid_policy`). Ці схеми описують реалізовану архітектуру й політику, а не експериментальні вимірювання."]
    write(RESULTS / "THESIS_FIGURES_UA.md", "\n".join(figures) + "\n")
    write(RESULTS / "EXPERIMENT_METHODS_UA.md", "# Методика відтворення\n\nКоманда: `make research-demo` або `powershell -File scripts/research-demo.ps1`. Seed: 20261103. Джерело: synthetic. Train/validation/test — неперетинні псевдонімні учасники 60/20/20. Ознаки обмежені колонками `ml.features.MODEL_FEATURES`; observed_until строго передує decision_at. Препроцесинг fit лише на train; два варіанти кожної ML-моделі обираються за validation Macro-F1; test оцінюється один раз. Статичний і правиловий baseline не мають LogLoss. Політика показує ймовірність явної переваги, а не очікуване поліпшення UX.\n\nСирі значення: `synthetic/models_comparison.csv`, `synthetic/ablation.csv`, `synthetic/evaluation_report.json`; параметри й версії: `config_snapshot.json`.\n")
    write(RESULTS / "LIMITATIONS_UA.md", "# Обмеження\n\nНемає наданих реальних добровільних міток або UX-спроб. Synthetic результати доводять лише працездатність пайплайна. Генератор навмисно задає зв'язок між ознаками й міткою, тому offline якість на таких даних не переноситься на людей. Псевдонімізація не гарантує анонімності. Малий реальний набір може не дозволити груповий поділ трьох класів; тоді статус MODEL_NOT_EVALUABLE. Початкова схема UX-спроби не містить часу запису, тому імпортер не може довести, що кожна спроба сталася після згоди; для реального досліду це потрібно забезпечити протоколом або розширенням контракту. У майбутньому UX-досліді треба врахувати ефект навчання, порядок умов, репрезентативність учасників і окреме погодження процедури. Автоматичні тести доступності не замінюють повний аудит WCAG 2.2 AA.\n")
    manifest = []
    for path in sorted(RESULTS.rglob("*")):
        if not path.is_file() or path.name == "ARTIFACT_MANIFEST.json": continue
        rel = path.relative_to(ROOT).as_posix()
        synthetic = rel.startswith("results/synthetic/") or path.name in {
            "split_manifest.json", "config_snapshot.json", "THESIS_TABLES_UA.md", "THESIS_FIGURES_UA.md", "EXPERIMENT_METHODS_UA.md"}
        source = "synthetic" if synthetic else "volunteer" if rel.startswith("results/real/") else "derived"
        manifest.append({"path": rel, "role": path.suffix.lstrip(".") or "artifact", "source": source,
                         "is_synthetic": synthetic, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (RESULTS / "ARTIFACT_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__": finalize()
