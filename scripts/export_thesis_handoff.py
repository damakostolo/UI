#!/usr/bin/env python3
"""Evidence-first thesis handoff from the current repository; no application rewrites."""
from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "thesis_handoff"
sys.path.insert(0, str(ROOT))
SOURCE_REQUEST = Path.home() / "Downloads" / "UI_ML_Handoff_Request.zip"
WARN = "СИНТЕТИЧНІ ДАНІ — НЕ Є ОЦІНКОЮ РЕАЛЬНИХ КОРИСТУВАЧІВ"
ORIGINS: dict[str, str] = {}


def write(rel: str, value: str | dict | list, origin: str = "scripts/export_thesis_handoff.py") -> Path:
    path = H / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, ensure_ascii=False, indent=2) + "\n" if isinstance(value, (dict, list)) else value.rstrip() + "\n"
    path.write_text(content, encoding="utf-8")
    ORIGINS[rel] = origin
    return path


def copy(src: str, dest: str) -> None:
    target = H / dest
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / src, target)
    ORIGINS[dest] = src


def csv_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(rel: str, rows: list[dict], columns: list[str], origin: str = "scripts/export_thesis_handoff.py") -> None:
    path = H / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    ORIGINS[rel] = origin


def line_of(file: str, text: str) -> int:
    for number, line in enumerate((ROOT / file).read_text(encoding="utf-8").splitlines(), 1):
        if text in line:
            return number
    raise ValueError(f"No source anchor {file}: {text}")


def source_archive() -> None:
    allowed_roots = ("backend", "ml", "frontend/src", "tests", "scripts", "contracts", "docs", "data/sample_synthetic", "data/templates")
    allowed_suffixes = {".py", ".ts", ".tsx", ".css", ".html", ".json", ".jsonl", ".csv", ".md", ".mmd", ".ps1", ".png", ".svg"}
    singles = ("README.md", "AGENTS.md", "START_HERE_CODEX.md", "Dockerfile", "Makefile", ".env.example", "requirements.txt", "requirements-linux.lock", "frontend/package.json", "frontend/package-lock.json", "frontend/tsconfig.json", "frontend/index.html")
    members = {ROOT / name for name in singles if (ROOT / name).is_file()}
    for root_name in allowed_roots:
        for path in (ROOT / root_name).rglob("*"):
            if path.is_file() and path.suffix in allowed_suffixes and not any(part in {"node_modules", "dist", "__pycache__", ".git", "real"} for part in path.parts):
                members.add(path)
    archive = H / "source_snapshot.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=8) as output:
        for path in sorted(members):
            output.write(path, path.relative_to(ROOT).as_posix())
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        compose = re.sub(r"(?m)^(\s*POSTGRES_PASSWORD:\s*).*$", r"\g<1>${UI_ML_DB_PASSWORD}", compose)
        compose = re.sub(r"(?m)^(\s*DATABASE_URL:\s*postgresql\+psycopg://[^:]+:)[^@]+(@.*)$", r"\g<1>${UI_ML_DB_PASSWORD}\g<2>", compose)
        output.writestr("docker-compose.example.yml", compose)
    ORIGINS["source_snapshot.zip"] = "whitelisted project sources; sanitized docker-compose.example.yml"


def inspect_data() -> tuple[dict, dict, list[dict]]:
    rows = csv_rows(ROOT / "data/sample_synthetic/feature_rows.csv")
    summary = json.loads((ROOT / "results/synthetic/dataset_summary.json").read_text(encoding="utf-8"))
    split = json.loads((ROOT / "results/split_manifest.json").read_text(encoding="utf-8"))
    if not all(row["source"] == "synthetic" and row["is_synthetic"].lower() == "true" for row in rows):
        raise ValueError("Synthetic training data provenance failed")
    if summary["n_rows"] != len(rows) or summary["n_participants"] != len({r["participant_id"] for r in rows}):
        raise ValueError("Dataset summary differs from input")
    if any(set(split[a]) & set(split[b]) for a, b in (("train_ids", "validation_ids"), ("train_ids", "test_ids"), ("validation_ids", "test_ids"))):
        raise ValueError("Participant split overlap")
    return summary, split, rows


def project_files(runtime: dict) -> None:
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or "UNKNOWN"
    head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    git = f"Гілка: {branch}\nHEAD: {head.stdout.strip() if head.returncode == 0 else 'UNBORN_HEAD — комітів немає'}\nСтатус: вихідні файли на момент аудиту не додані до Git; commit history не дає фактичних годин роботи.\n"
    write("01_project/git_info.txt", git, "git branch; git rev-parse --verify HEAD; git status --short")
    exclusions = {"node_modules", "dist", "__pycache__", ".pytest_cache", ".git", "thesis_handoff", "data/real"}
    tree = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file() and not any(part in exclusions for part in p.relative_to(ROOT).parts) and not p.name.startswith(".e2e"))
    write("01_project/project_tree.txt", "\n".join(tree), "current repository file inventory")
    write("01_project/architecture_overview.md", """# Фактична архітектура

React/TypeScript/Vite рендерить шість віджетів і три макети. Перший екран статичний. За явної дії клієнт створює псевдонімний профіль у FastAPI, передає контрольовані події та запитує рекомендацію. FastAPI перевіряє bearer token і згоду, зберігає дозволені записи через SQLAlchemy. Локально можна використати SQLite; Docker Compose піднімає PostgreSQL.

Дослідницький пакет `ml/` окремо формує predecision ознаки, розбиває синтетичні приклади за учасником, навчає моделі, оцінює test і записує артефакти `results/`. Runtime hybrid завантажує лише явно позначену синтетичну demo модель. Рекомендація сама не змінює UI: accept, reject та undo керуються окремими діями.

Код: `frontend/src/App.tsx`, `frontend/src/layouts.ts`, `backend/app.py`, `ml/features.py`, `ml/research.py`, `ml/policy.py`. Діаграми у `03_design/diagrams/`.

Обмеження: ORM викликає `create_all` під час імпорту; окремих міграцій немає. UI не проходив повний ручний аудит WCAG 2.2 AA.
""")
    versions = runtime["packages"]
    lines = ["# Стек і версії", "", f"ОС аудиту: `{runtime['os']}`; Python `{runtime['python']}`; Node `{runtime['node']}`; npm `{runtime['npm']}`.", "", "| Компонент | Версія |", "|---|---|"]
    lines += [f"| {name} | {version} |" for name, version in versions.items()]
    lines += ["", "React/Vite/TypeScript і решта frontend-залежностей зафіксовані у `source_snapshot.zip:frontend/package-lock.json`. Python Linux-контейнер використовує `requirements-linux.lock`. Наведені версії Python — фактично встановлені під час аудиту.\n"]
    write("01_project/stack_and_versions.md", "\n".join(lines), "01_project/run_environment.json; frontend/package-lock.json; requirements-linux.lock")
    write("01_project/run_environment.md", f"# Середовище запуску\n\nUTC фіксації: `{runtime['captured_utc']}`. ОС `{runtime['os']}`, Python `{runtime['python']}`, логічних CPU `{runtime['logical_cpus']}`. Детальні версії — `run_environment.json`. Тестування виконано у Windows; окремо перевірено локальний Docker Compose. Конкретні характеристики диска, енергоспоживання й ціни не вимірювалися.\n")
    write("01_project/commands_reproduction.md", """# Команди відтворення

Із кореня репозиторію: `python -m pip install -r requirements.txt`; `cd frontend && npm ci`; `powershell -ExecutionPolicy Bypass -File scripts/research-demo.ps1` або `make research-demo`; `python -m pytest -q`; `python scripts/check_deliverables.py --strict`; `cd frontend && npm run typecheck && npm test && npm run build`; `python tests/e2e_browser.py` за наявності Chrome. Docker: `docker compose up -d --build`, локальні адреси 15173/18000.

Аудит цієї передачі: `python scripts/handoff_audit.py`, `python scripts/handoff_capture.py`, `python scripts/handoff_benchmark.py`, `python scripts/export_thesis_handoff.py`, `python 09_reproducibility/export_scripts/check_handoff.py thesis_handoff`. Фактичні stdout/stderr і exit code — `05_tests/`.

Реальні дані: `python scripts/research_real.py --bundle <каталог>` лише після погодженої процедури та згоди; ця команда в аудиті з реальним набором не виконувалася.
""")


def research_files(summary: dict, split: dict, input_rows: list[dict]) -> None:
    raw_copies = {
        "data/sample_synthetic/feature_rows.csv": "02_research/input/feature_rows_synthetic.csv",
        "data/sample_synthetic/events.jsonl": "02_research/input/events_example_synthetic.jsonl",
        "data/sample_synthetic/trials.csv": "02_research/input/trials_example_synthetic.csv",
        "data/sample_synthetic/dataset_manifest.json": "02_research/input/dataset_manifest_synthetic.json",
        "results/synthetic/evaluation_report.json": "02_research/raw_results/evaluation_report.json",
        "results/synthetic/dataset_summary.json": "02_research/raw_results/dataset_summary.json",
        "results/synthetic/environment.json": "02_research/raw_results/environment.json",
        "results/synthetic/system_benchmark.json": "02_research/raw_results/system_benchmark_historical.json",
        "results/synthetic/feature_summary.csv": "02_research/raw_results/feature_summary.csv",
        "results/config_snapshot.json": "02_research/raw_results/config_snapshot.json",
    }
    for src, dest in raw_copies.items():
        copy(src, dest)
    for src, dest in (("results/synthetic/dataset_card.md", "02_research/dataset_card.md"),
                      ("results/split_manifest.json", "02_research/split_manifest.json"),
                      ("results/synthetic/models_comparison.csv", "02_research/models_comparison.csv"),
                      ("results/synthetic/policy_metrics.csv", "02_research/hybrid_policy_metrics.csv"),
                      ("results/synthetic/ablation.csv", "02_research/ablation_results.csv")):
        copy(src, dest)
    for figure in (ROOT / "results/synthetic").glob("*"):
        if figure.suffix in {".png", ".svg"}:
            copy(figure.relative_to(ROOT).as_posix(), f"02_research/figures/{figure.name}")
    first, last = min(r["decision_at"] for r in input_rows), max(r["decision_at"] for r in input_rows)
    inventory = [
        {"dataset": "feature_rows_synthetic", "path": "02_research/input/feature_rows_synthetic.csv", "source_kind": "synthetic", "participants": summary["n_participants"], "sessions": len({r["session_id"] for r in input_rows}), "rows": len(input_rows), "class_counts": json.dumps(summary["class_counts"], ensure_ascii=False), "time_range_utc": f"{first} … {last}", "consent": "demo-synthetic; no human consent", "rights_or_basis": "generated locally for software testing", "sha256": hashlib.sha256((ROOT / "data/sample_synthetic/feature_rows.csv").read_bytes()).hexdigest(), "notes": WARN},
    ]
    for name, path in (("events_example_synthetic", "data/sample_synthetic/events.jsonl"), ("trials_example_synthetic", "data/sample_synthetic/trials.csv")):
        n = sum(bool(line.strip()) for line in (ROOT / path).read_text(encoding="utf-8").splitlines()) - (1 if path.endswith(".csv") else 0)
        inventory.append({"dataset": name, "path": "02_research/input/" + Path(path).name.replace("events.jsonl", "events_example_synthetic.jsonl").replace("trials.csv", "trials_example_synthetic.csv"), "source_kind": "synthetic", "participants": "NOT_APPLICABLE", "sessions": "NOT_APPLICABLE", "rows": n, "class_counts": "NOT_APPLICABLE", "time_range_utc": "see source file", "consent": "demo-synthetic", "rights_or_basis": "test fixture", "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), "notes": "Not used to train offline models"})
    for path in sorted((ROOT / "data/templates").glob("*")):
        inventory.append({"dataset": path.stem, "path": "06_real_ux/templates/" + path.name, "source_kind": "documentation", "participants": "0", "sessions": "0", "rows": "0", "class_counts": "NOT_APPLICABLE", "time_range_utc": "NOT_APPLICABLE", "consent": "blank template", "rights_or_basis": "project template", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "notes": "Blank template only; not an observed dataset"})
    inventory.append({"dataset": "real_volunteer_data", "path": "NOT_AVAILABLE", "source_kind": "unknown", "participants": "NOT_AVAILABLE", "sessions": "NOT_AVAILABLE", "rows": "NOT_AVAILABLE", "class_counts": "NOT_AVAILABLE", "time_range_utc": "NOT_AVAILABLE", "consent": "NOT_AVAILABLE", "rights_or_basis": "NOT_AVAILABLE", "sha256": "NOT_AVAILABLE", "notes": "REAL_UX_NOT_CONDUCTED; only blank templates present"})
    write_csv("02_research/data_inventory.csv", inventory, list(inventory[0]))
    manifest = json.loads((ROOT / "data/sample_synthetic/dataset_manifest.json").read_text(encoding="utf-8"))
    missing = {key: sum(row.get(key, "") in ("", None) for row in input_rows) for key in input_rows[0]}
    missing = {key: value for key, value in missing.items() if value}
    write("02_research/dataset_card.md", f"""# Картка набору: тільки СИНТЕТИЧНІ дані

{WARN}. Генератор `scripts/generate_synthetic_data.py:generate`; seed `{manifest['seed']}`, параметри `n_participants={manifest['n_participants']}`, `per_participant=3`, базова дата 2026-10-01 UTC. Набір містить {len(input_rows)} рядків, {manifest['n_participants']} **штучних** псевдоучасників і {manifest['n_sessions']} сесій. Мітки `{json.dumps(manifest['class_counts'], ensure_ascii=False)}`; найбільший клас compact, найменший standard. Діапазон `decision_at`: `{first}` … `{last}`. Пропуски полів за перевіркою CSV: `{json.dumps(missing, ensure_ascii=False)}`. SHA-256 вхідного CSV: `{inventory[0]['sha256']}`.

Алгоритм генерації: для кожного штучного ID випадкова прихована базова перевага; збільшення task-open для focus, report-open для standard, quick-action для compact; мітка дорівнює базовій у більшості випадків, інакше обирається випадково. Інші агрегати/категорії генеруються локальним RNG. Штучна кореляція задумана лише для перевірки pipeline; вона не вимірює людей. `label_source=synthetic_generator`, `source=synthetic`, `is_synthetic=true`, `consent_version=demo-synthetic`; реальна інформована згода тут не застосовується.

Права використання: локальний згенерований матеріал проєкту для інженерної перевірки, без сторонніх персональних даних. Дату фактичного створення початкового CSV окремим журналом не засвідчено; часові поля всередині рядків — штучні. Реальні явні `preferred_layout`, trial і SUS відсутні. Приклад `events.jsonl` і `trials.csv` — окремі тестові фікстури, не навчальна вибірка. Повний перелік файлів і хешів — `data_inventory.csv`.
""")
    features = csv_rows(ROOT / "results/feature_dictionary.csv")
    numeric = {"opens_tasks_7d", "opens_reports_7d", "quick_actions_7d", "avg_actions_per_session_7d", "active_sessions_7d", "prior_undo_rate"}
    enhanced = [{"feature": r["feature"], "definition": r["definition"], "type": "numeric" if r["feature"] in numeric else "categorical", "available_at": r["available_at"], "missing_policy": r["missing_policy"], "module_path": "ml/features.py:MODEL_FEATURES; ml/research.py:pipeline"} for r in features]
    write_csv("02_research/feature_dictionary.csv", enhanced, list(enhanced[0]), "results/feature_dictionary.csv; ml/features.py; ml/research.py")
    write("02_research/research_problem_and_math.md", """# Формалізація фактично реалізованої задачі

`L={standard, compact, focus}` (`ml/features.py:LAYOUTS`). Для псевдонімного учасника `u` і моменту рішення `t` вектор `x=φ(H_u(≤observed_until), context_t)` має лише ознаки з `ml/features.py:MODEL_FEATURES`. Обов'язкова умова `observed_until < decision_at=t`; `ml/features.py:validate_predecision` її перевіряє. Ціль `y=preferred_layout`. У синтетичному наборі `y` генерує `scripts/generate_synthetic_data.py`; явних реальних міток немає.

Offline класифікатор дає `p(l|x)`. Реалізація `ml/policy.py:decide` бере `l*=argmax_l p(l|x)`; за рівності порядок визначає перелік `LAYOUTS`. При `l*=current`, недостатній кількості подій, активному завданні, cooldown, вимкненні, відсутній моделі, `max p<0.55` або `p(l*)-p(current)<0.15` результат `no_change`. Інакше `propose`, після якого UI потребує окремого accept. Модельна різниця ймовірностей не є очікуваним приростом UX.

Метрики offline: `Accuracy=correct/n`; macro-Precision/Recall/F1 — невиважене середнє трьох класів; `LogLoss=−(1/n)Σ_i log p(y_i|x_i)` лише для моделей з імовірностями. `ml/research.py:score` використовує однаковий test subset.

Розходження з `docs/MATH_MODEL.md`: запланований штраф `λ·C(l,current)` у виборі кандидата в коді **не реалізовано**. Значення `λ` не підбиралося. Цю формулу не слід описувати як реалізовану.
""")
    write("02_research/preprocessing_and_labels.md", """# Ознаки, препроцесинг і походження міток

`ml/features.py:build_feature_row` вибирає дозволені події того самого учасника за сім діб до `observed_until`, причому `occurred_at < decision_at`. Агрегати: кількість відкриттів `tasks/reports`, швидких дій, число різних сесій, `len(events)/max(n_sessions,1)`, частка undo серед accept+undo, останні категорії пристрою/екрана і частина доби. За відсутності подій кількості та частка дорівнюють 0, категорії — `unknown`.

`ml/research.py:pipeline` заповнює числові пропуски медіаною і стандартизує; категоріальні — найчастішим значенням та OneHotEncoder з `handle_unknown=ignore`. Fit виконується лише на train. Список модельних входів виключає `participant_id`, `session_id`, `preferred_layout`, `elapsed_ms`, `completed`, `active_task` і майбутні результати. Тести `tests/test_research.py` перевіряють часову межу та неперетин груп.

У `scripts/generate_synthetic_data.py` штучна прихована категорія впливає і на ознаки, і на псевдомітку; це навмисна інженерна перевірка. Реальний імпортер `scripts/import_real_data.py` вимагає `label_source=explicit_preference` та документованої згоди. Пакета таких даних немає. Runtime inference у `backend/app.py:recommend` обчислює частину ознак інакше: `prior_undo_rate=0`, `time_of_day_bin=day`; це обмежує перенесення offline оцінки на робочий UI.
""")
    groups = {key: len(split[key]) for key in ("train_ids", "validation_ids", "test_ids")}
    write("02_research/split_protocol.md", f"# Протокол поділу\n\nSeed `{split['seed']}`. `ml/research.py:split_participants` сортує псевдонімні participant_id, перемішує NumPy RNG і бере приблизно 60/20/20. Групи: train {groups['train_ids']}, validation {groups['validation_ids']}, test {groups['test_ids']}; за 3 рядки на учасника це 216/72/72 рядків. Попарні перетини порожні (`disjoint=true`). Класовий склад: `{json.dumps(split['class_counts'], ensure_ascii=False)}`. Повні **синтетичні** ID збережено у `split_manifest.json`.\n\nКожний рядок має `observed_until < decision_at`. Часового holdout між учасниками немає; поділ за групами випадковий. Препроцесор навчається на train; 2 варіанти кожної ML-моделі обираються за validation Macro-F1; test використовується один раз після вибору в межах скрипта. `scripts/handoff_reproducibility.py` незалежно повторно обчислює метрики і звіряє матриці та split.\n")
    comparison = csv_rows(ROOT / "results/synthetic/models_comparison.csv")
    write("02_research/model_training_and_parameters.md", """# Фактично навчальні стратегії

`ml/research.py:pipeline` створює спільний `ColumnTransformer` для numeric/categorical ознак. `static`: завжди `standard`; `rule`: `quick_actions_7d≥8 → compact`, інакше `opens_tasks_7d≥10 → focus`, інакше `standard` (`ml/policy.py:rule_layout`). Ці два baseline не мають валідного LogLoss. LogisticRegression: `C∈{0.3,1.0}`, `max_iter=500`; RandomForest: `(n_estimators,max_depth)∈{(80,5),(120,8)}`; XGBClassifier: `(80,3)` або `(120,4)`, `learning_rate=0.08`, `multi:softprob`, `num_class=3`, `eval_metric=mlogloss`. Seed `20261103`, `n_jobs=1` для деревних моделей. Вибір варіанта лише за validation Macro-F1.

Для XGBoost мітки кодуються у 0/1/2 у порядку `standard, compact, focus`. `Pipeline` для кожної ML-моделі fit лише на train. Версії пакунків: `01_project/stack_and_versions.md`; вибрані варіанти й test-метрики: `models_comparison.csv`. Збережена runtime demo-модель — logistic regression, навчена лише на синтетичних даних; реальний production registry відсутній.
""")
    write("02_research/model_metrics_details.md", f"# Деталі offline оцінювання\n\n{WARN}. Всі п'ять стратегій оцінені на тих самих {len(split['test_ids'])} синтетичних учасниках і 72 test рядках. Метрики та single-batch latency збережені без округлення у `models_comparison.csv`; confusion matrices — `confusion_matrices.csv` та `raw_results/evaluation_report.json`. LogLoss для static/rule порожній за визначенням. `coverage=1` у моделі означає, що прогноз повернуто для кожного test-рядка; policy coverage окремо в `ablation_results.csv`.\n\nLatency в історичному CSV є одноразовим локальним заміром, а не p50/p95. Новий контрольований замір 30 повторів подано в `05_tests/performance_benchmarks.csv`; це технічна швидкодія, не UX.\n")
    report = json.loads((ROOT / "results/synthetic/evaluation_report.json").read_text(encoding="utf-8"))
    matrix_rows = []
    labels = ("standard", "compact", "focus")
    for model, matrix in report["confusion_matrices"].items():
        for i, true_label in enumerate(labels):
            for j, predicted_label in enumerate(labels):
                matrix_rows.append({"model": model, "true_label": true_label, "predicted_label": predicted_label,
                                    "count": matrix[i][j], "test_n": report["test_rows"], "source_kind": "synthetic", "is_synthetic": "true"})
    write_csv("02_research/confusion_matrices.csv", matrix_rows, list(matrix_rows[0]), "results/synthetic/evaluation_report.json")
    write("02_research/hybrid_algorithm_and_pseudocode.md", """# Гібридна політика — фактичний код

Параметри `ml/policy.py:PolicyConfig`: `min_events=5`, `min_confidence=0.55`, `min_probability_gain=0.15`, `cooldown_hours=24`. Обов'язкові шість віджетів видимі в усіх макетах; `active_task=true` забороняє пропозицію; `enabled=false` дає `no_change`; відсутня модель — `model_unavailable`. Підтвердження, відхилення, Undo й вимкнення керуються UI та `backend/app.py:transition`. Runtime ML доступний тільки в явно позначеному synthetic demo.

```text
candidate = argmax(probabilities[l] for l in LAYOUTS)
reasons = []
if not enabled: reasons += user_disabled
if not model_available: reasons += model_unavailable
if event_count < 5: reasons += cold_start
if active_task: reasons += active_task
if confirmed_change_within_24h: reasons += cooldown
if candidate == current: reasons += same_layout
if p(candidate) < .55: reasons += low_confidence
if p(candidate) - p(current) < .15: reasons += low_gain
if reasons: return no_change(current, reasons)
return propose(candidate)  # UI змінюється лише після accept; undo відновлює current
```

Файл `policy_trace_synthetic.json` — результат виконаного локального **автоматизованого** сценарію в тимчасовій БД: 8 тестових quick_action, правило запропонувало compact, UI підтвердив і повернув standard через Undo. Цей trace не є поведінкою людини або виміром UX.
""")
    write("02_research/errors_and_limitations.md", """# Помилки, обмеження і загрози валідності

1. Реальних добровільних міток, учасників і UX-спроб немає: `REAL_UX_NOT_CONDUCTED`. Synthetic Macro-F1/accuracy не доводять покращення часу, дій або зручності.
2. Генератор задає спільний прихований механізм ознак і міток; якість на ньому не переноситься на людей. Дисбаланс класів: 91/146/123 рядків.
3. `docs/MATH_MODEL.md` планує штраф вартості перестановки `λC`, але `ml/policy.py:decide` його не реалізує. Параметри політики в абляції не підбиралися на validation.
4. Runtime ознаки в `backend/app.py:recommend` не тотожні offline: `prior_undo_rate=0`, `time_of_day_bin=day`. Немає перевірки калібрування ймовірностей на людях.
5. В `ml/research.py` немає time-based sensitivity analysis і bootstrap інтервалів; випадкове розбиття лише за учасником. Тестовий набір не використовується для підбору моделей у коді, але обрана для абляції logistic regression фіксована за реалізацією, а не за окремим протоколом вибору для UX.
6. Абляція — replay по синтетичних рядках без реальних active_task/cooldown/acceptance історій. Нуль автоматичних змін на повній політиці означає вимогу підтвердження, не нуль прийнятих людьми змін.
7. UX trial schema не має часу запису, тому імпортер не може довести, що кожна спроба відбулася після згоди. Окремих міграцій БД немає. Повний WCAG 2.2 AA аудит не проведено.
""")


def design_files() -> None:
    for src, name in (("docs/SPECIFICATION.md", "requirements_source.md"),
                      ("docs/ARCHITECTURE_AND_API.md", "architecture_api_source.md"),
                      ("docs/EXPERIMENT_PROTOCOL.md", "experiment_protocol_source.md")):
        copy(src, f"03_design/source_docs/{name}")
    for diagram in (ROOT / "docs/diagrams").glob("*"):
        copy(diagram.relative_to(ROOT).as_posix(), f"03_design/diagrams/{diagram.name}")
    copy("docs/diagrams/erd.mmd", "03_design/database_erd.mmd")
    # OpenAPI is generated from the imported FastAPI application, not transcribed.
    os.environ.setdefault("DATABASE_URL", "sqlite://")
    from backend.app import app
    write("03_design/api_openapi.json", app.openapi(), "backend.app:app.openapi()")
    write("03_design/requirements.md", """# Перевірені вимоги та межі

Джерело вимог: `source_docs/requirements_source.md`; реалізація перевірена за `backend/app.py`, `frontend/src/App.tsx`, `ml/policy.py`. Є три макети, шість постійних віджетів, static/rule/hybrid, явна згода, заборона запису подій без згоди, підтвердження рекомендації, reject/undo, пауза/вимкнення, видалення профілю і статичний fallback. Автоматичне прийняття пропозиції не реалізоване. Повний аудит доступності, мобільні ручні сесії та дослідження з добровольцями не проведені.

Статус вимоги та доказ для конкретної тези див. `../EVIDENCE_MAP.csv`. Діаграми — версія з наявного `docs/diagrams/`; їх слід читати разом із фактичним кодом, якщо документація розходиться з ним.
""")
    write("03_design/modules_and_dataflows.md", """# Модулі і потоки даних

`frontend/src/App.tsx` керує режимом, згодою, контрольованими подіями та переходами. `frontend/src/layouts.ts` задає три структури макетів. `backend/app.py` містить REST, Pydantic-валідацію, ORM і перевірку bearer/consent; SQLAlchemy використовує SQLite локально або PostgreSQL у Compose. `ml/features.py` розраховує 7-денні агрегати; `ml/research.py` проводить offline навчання; `ml/policy.py` формує рішення; `scripts/research_demo.py` керує дослідницьким запуском.

Потік: явна згода → контрольована подія → збереження → побудова ознак → прогноз або правило → перевірка порогів/стабільності → пропозиція → accept/reject → можливий undo. При відкликанні згоди сервер блокує подальші події. Схеми: `diagrams/system_context`, `component`, `use_cases`, `sequence_recommendation`, `activity_hybrid_policy`, `erd` у `.mmd` і `.svg/.png`.
""")
    write("03_design/db_schema.md", """# Фактична схема БД

Вісім ORM-таблиць у `backend/app.py`: `participants`, `consents`, `events`, `layout_states`, `recommendations`, `study_trials`, `model_runs`, `model_artifacts`. Точні стовпці, типи, PK/FK та індекси згенеровано у `db_schema.json` з SQLAlchemy metadata. Діаграма — `database_erd.mmd` і `diagrams/erd.svg`.

Таблиці створюються `Base.metadata.create_all`; окремих міграцій немає. `DELETE /api/v1/profile/me` видаляє записи поточного псевдонімного профілю; перевірка в тестах і E2E. Це не свідчить про керовану retention-політику реального дослідження.
""")
    from backend.app import Base
    schema = []
    for table in Base.metadata.sorted_tables:
        schema.append({"table": table.name,
                       "columns": [{"name": c.name, "type": str(c.type), "primary_key": c.primary_key,
                                    "nullable": c.nullable, "foreign_keys": [str(f.target_fullname) for f in c.foreign_keys]} for c in table.columns],
                       "indexes": [{"name": i.name, "columns": [c.name for c in i.columns], "unique": i.unique} for i in table.indexes]})
    write("03_design/db_schema.json", schema, "backend.app:Base.metadata")
    paths = app.openapi()["paths"]
    endpoints = [f"| `{method.upper()}` | `{route}` | {op.get('summary', '')} |" for route, methods in paths.items() for method, op in methods.items() if method.lower() in {"get", "post", "delete", "put", "patch"}]
    write("03_design/api_description.md", "# Фактичний REST API\n\nДжерело: `api_openapi.json`, створено `backend.app:app.openapi()` під час експорту. Для всіх приватних маршрутів потрібен bearer token псевдонімного профілю; для подій, рекомендацій і study trial — чинна згода. Точні body, відповіді та schema-validation див. OpenAPI; демонстраційні payload у `api_examples_synthetic.json`.\n\n| Метод | Шлях | Опис |\n|---|---|---|\n" + "\n".join(endpoints) + "\n\nТипові помилки: 401/403 для відсутнього token/consent, 404 для чужого або відсутнього ресурсу, 422 для невалідного body. Точний набір response codes по кожному шляху — OpenAPI і `backend/app.py`; опис тут не замінює runtime перевірку.\n")
    write("03_design/api_examples_synthetic.json", {"synthetic": True, "notice": WARN, "consent": {"version": "demo-1"}, "event": {"event_id": "event_demo_000001", "participant_id": "participant_demo_000001", "session_id": "session_demo_000001", "occurred_at": "2026-01-01T12:00:00Z", "event_type": "quick_action", "widget_id": "quick_actions", "source": "synthetic", "is_synthetic": True, "consent_version": "demo-1", "device_category": "desktop", "viewport_category": "large"}}, "illustrative examples; validated against EventIn/ConsentIn")


def implementation_files() -> None:
    modules = [
        ("frontend/src/App.tsx", "export default function App", "UI: стани згоди, режимів і рекомендацій"),
        ("frontend/src/layouts.ts", "export const orders", "Макети і віджети"),
        ("frontend/src/style.css", ":root", "Адаптивне оформлення"),
        ("backend/app.py", "class AnonymousParticipant", "ORM профілю"),
        ("backend/app.py", "def consent_required", "Серверна перевірка згоди"),
        ("backend/app.py", "def add_event", "Валідація і збереження подій"),
        ("backend/app.py", "def recommend", "Runtime рекомендація"),
        ("backend/app.py", "def transition", "Accept/reject/undo"),
        ("ml/features.py", "def build_feature_row", "Агрегація ознак"),
        ("ml/research.py", "def split_participants", "Груповий поділ"),
        ("ml/research.py", "def evaluate", "Навчання, оцінка, артефакти"),
        ("ml/policy.py", "def decide", "Пороги і захист від перемикання"),
    ]
    lines = ["# Модулі для додатків", "", "`file:line` звірено під час експорту; вихідний код — `../source_snapshot.zip`.", "", "| Модуль | Роль |", "|---|---|"]
    for path, anchor, role in modules:
        try:
            lines.append(f"| `{path}:{line_of(path, anchor)}` | {role} |")
        except ValueError:
            lines.append(f"| `{path}` | {role}; точну декларацію перевірити вручну |")
    write("04_implementation/code_modules_for_appendix.md", "\n".join(lines))
    write("04_implementation/implemented_features.md", """# Реалізовані функції

Поточний застосунок має три responsive макети `standard/compact/focus`, шість віджетів, статичний і rule режими, hybrid із синтетичною demo logistic regression, явне ввімкнення та відкликання згоди, контрольовані події, пропозицію з ручним підтвердженням, reject/undo, паузу й вимкнення персоналізації, статичний fallback, експорт і видалення власного псевдонімного профілю. Сервер перевіряє згоду перед записом події. Докази: код у `source_snapshot.zip`, E2E лог, 10 реальних скриншотів тестового сценарію.

Відсутні реальні поведінкові дані, production-тренування й міграції БД. Застосунок прототип дослідження, а не підтверджена UX-система для людей.
""")
    captions = [
        "Статичний режим: стандартний макет без профілю", "Статичний компактний макет", "Статичний фокусний макет",
        "Явне ввімкнення згоди в тестовому профілі", "Вибрано rule режим у тестовому профілі", "Пропозиція compact після 8 тестових quick_action",
        "Відхилення пропозиції", "Підтверджений compact", "Undo повернув standard", "Згоду відкликано; тестовий профіль потім видалено"]
    shots = sorted((H / "04_implementation/screenshots").glob("*.png"))
    if len(shots) != 10:
        raise ValueError(f"Expected 10 actual browser captures, found {len(shots)}")
    write("04_implementation/screenshots_index.md", "# Реальні скриншоти локального UI\n\nЗнято Playwright/Chrome після запуску Vite і FastAPI на одноразовій SQLite; сценарій автоматизований і синтетичний, учасників-людей не було. Джерело `scripts/handoff_capture.py`; trace `../02_research/policy_trace_synthetic.json`.\n\n" + "\n".join(f"{i}. `{shot.name}` — {caption}. {WARN}." for i, (shot, caption) in enumerate(zip(shots, captions), 1)))
    write("04_implementation/ui_scenarios.md", """# Пройдені сценарії UI

Автоматизований браузерний сценарій: static standard → compact → focus; створення одноразового профілю → явна згода → rule режим → 8 синтетичних quick_action → preview пропозиції compact → reject → повторна пропозиція → accept → undo → відкликання згоди → видалення тестового профілю. Скриншоти 01–10 та синтетичний trace збережено. Це виконання коду, а не користувацьке дослідження. Окремий браузерний E2E (`tests/e2e_browser.py`) завершився PASS; лог — `../05_tests/raw_logs/browser_e2e.stdout.txt`.
""")


def test_files() -> None:
    commands_path = H / "05_tests/commands_and_status.csv"
    commands = csv_rows(commands_path)
    first = csv_rows(H / "05_tests/commands_attempt1.csv")
    failed = [r for r in first if r["status"] == "FAIL" and r["name"] == "synthetic_repro"]
    if len(failed) != 1:
        raise ValueError("First failure evidence missing")
    failed[0]["name"] = "synthetic_repro_attempt1"
    failed[0]["stdout_log"] = "05_tests/raw_logs/synthetic_repro_attempt1.stdout.txt"
    failed[0]["stderr_log"] = "05_tests/raw_logs/synthetic_repro_attempt1.stderr.txt"
    commands = failed + [r for r in commands if r["name"] != "synthetic_repro_attempt1"]
    capture_log = H / "05_tests/raw_logs/browser_capture.stdout.txt"
    if capture_log.exists() and not any(r["name"] == "browser_capture" for r in commands):
        # Capture completed in a separate earlier process; the UTC timestamp is recovered from file mtime.
        when = datetime.fromtimestamp(capture_log.stat().st_mtime, timezone.utc)
        commands.append({"name": "browser_capture", "command": "python scripts/handoff_capture.py", "status": "PASS", "exit_code": 0,
                         "started_utc": "NOT_AVAILABLE", "ended_utc": when.isoformat(), "started_local": "NOT_AVAILABLE", "ended_local": when.astimezone().isoformat(),
                         "os": platform.platform(), "stdout_log": "05_tests/raw_logs/browser_capture.stdout.txt", "stderr_log": "05_tests/raw_logs/browser_capture.stderr.txt"})
    write_csv("05_tests/commands_and_status.csv", commands, list(commands[0]))
    counts = Counter(r["status"] for r in commands)
    report = ["# Звіт перевірок", "", f"Поточний експорт містить {counts['PASS']} PASS, {counts['FAIL']} FAIL, {counts['BLOCKED']} BLOCKED. Один FAIL — перша спроба нового контрольного скрипта (`synthetic_repro_attempt1`), виправлена зміною шляху імпорту; повторне відтворення PASS. Перший запуск audit runner завершився FileNotFoundError при записі середовища; журнал `raw_logs/audit_runner_attempt1.stderr.txt`. Він не змінював код застосунку.", "", "| Команда | Статус | Exit code | stdout | stderr |", "|---|---|---:|---|---|"]
    for row in commands:
        report.append(f"| `{row['name']}` | {row['status']} | {row['exit_code']} | `{row['stdout_log']}` | `{row['stderr_log']}` |")
    report += ["", "Окремі невдалі спроби службового експортера — `export_attempts.md`; вони не належать до тестів застосунку.", "", "Pytest: 11 passed, 1 стороннє DeprecationWarning; Vitest: 1 файл, 1 тест PASS. Typecheck, build, E2E, валідатор вхідного набору, нормальна й strict перевірки deliverables та Compose config пройшли. Не проводився ручний повний WCAG аудит і запуск з реальними добровольцями. Логи збережені без необроблених IP, токенів або реальної БД."]
    write("05_tests/test_report.md", "\n".join(report))
    write("05_tests/performance_method.md", """# Метод виміру швидкодії

`scripts/handoff_benchmark.py` фактично запущено в локальному Windows-середовищі; версії/CPU у `performance_environment.json`, лог команди в `raw_logs/performance_benchmark.stdout.txt`. Після 5 warmup зроблено 30 повторів кожної операції, вимір `time.perf_counter_ns`; p50/p95 обчислено NumPy percentile. Перший замір: `predict_proba` demo logistic regression на batch із 72 **синтетичних** test-рядків; окремо подано latency на рядок діленням на 72. Другий: `GET /api/v1/health` через in-process FastAPI TestClient, без мережі, браузера чи БД. Одиниці мс. Машинні значення — `performance_benchmarks.csv`.

Це локальна технічна швидкодія; її не можна подавати як час відгуку у віддаленого користувача, завдання UX або статистику продуктивності production-сервера. Історичні single-batch latency з `models_comparison.csv` мають іншу методику.
""")


def real_ux_files() -> None:
    (H / "06_real_ux/figures").mkdir(parents=True, exist_ok=True)
    write("06_real_ux/README_ACTUAL_STATUS.md", """# REAL_UX_NOT_CONDUCTED

У репозиторії немає правомірно отриманого набору добровольців, реальних `preferred_layout`, фактичних UX trials або повних 10 відповідей SUS. `data/real` і `results/real` містять лише інструкції/порожні шаблони. Тому `real_trials_anonymized.csv`, `real_ux_summary.csv` і графіки з людських спостережень **не створені**. N реальних людей і оцінки UX — `NOT_AVAILABLE`.

Скриншоти і policy trace — локальний автоматизований тест із синтетичними діями, а не проведене дослідження. Висновок про поліпшення часу, кількості дій, SUS чи прийнятності персоналізації є `insufficient evidence`.
""")
    copy("docs/EXPERIMENT_PROTOCOL.md", "06_real_ux/ux_study_protocol.md")
    for src, dest in (("data/templates/participant_preference_blank.csv", "participant_preference_blank.csv"),
                      ("data/templates/ux_trials_blank.csv", "ux_trials_blank.csv"),
                      ("data/templates/real_data_manifest.example.json", "real_data_manifest.example.json"),
                      ("docs/CONSENT_TEXT_UA.md", "consent_text_template.md")):
        if (ROOT / src).exists():
            copy(src, "06_real_ux/templates/" + dest)
    write("06_real_ux/real_data_provenance.md", """# Походження реальних даних

`NOT_AVAILABLE — REAL_UX_NOT_CONDUCTED`. Перед заповненням розділу 4 автор має надати підтверджену процедуру згоди/етичного дозволу, псевдонімізовані події та мітки явних переваг з датами й версією схеми, порядок умов і trial-результати, а для SUS — усі 10 відповідей кожного учасника. Не включати ПІБ, email, IP, сирі тексти полів або токени. Наявні порожні шаблони в `templates/` не засвідчують проведення експерименту.
""")


def economic_files(runtime: dict) -> None:
    write("07_economics/actual_resources.md", f"""# Фактично зафіксовані ресурси

Середовище аудиту: {runtime['os']}; Python {runtime['python']}; Node {runtime['node']}; npm {runtime['npm']}; логічні CPU {runtime['logical_cpus']}. Повний snapshot версій — `../01_project/run_environment.json`. Локальний Docker Compose описує PostgreSQL і застосунок, `docker compose config --quiet` PASS; оплачувана хмара не використовувалася в цьому аудиті. Вартість устаткування, електроенергії, інфраструктури й ліцензій: `NOT_AVAILABLE`, платіжних документів немає. Окремий GPU не задокументовано; споживання пам'яті й енергії не вимірювалося.
""")
    write("07_economics/actual_worklog_or_unknown.md", "# Облік фактичної праці\n\n`ACTUAL_HOURS_UNKNOWN`. У наявному репозиторії HEAD ще не створено; коміти не дозволяють реконструювати трудовитрати. Worklog/timesheets або підписаних журналів часу немає. Час виконання тестів — машинний час аудиту і не дорівнює годинам розробки.\n")
    write("07_economics/economic_assumptions.md", """# Припущення для майбутнього розрахунку (ESTIMATE)

| Величина | Припущення | Джерело факту |
|---|---|---|
| Години розробки | `UNKNOWN`, ввести з worklog автора | Немає |
| Ставка за годину | `UNKNOWN`, ввести з обґрунтованого джерела | Немає |
| Вартість інфраструктури | `UNKNOWN`, підтвердити рахунками | Немає |
| Ліцензії | `UNKNOWN`, перевірити фактичні умови | Немає |
| Електроенергія | `UNKNOWN`, потрібні кВт·год і тариф | Немає |

Формула сценарію: `estimated_total = hours×rate + infrastructure + licences + electricity`. Жодне числове значення тут не подано як фактичні витрати. Порівняння із альтернативами і економічний ефект можна обчислити лише після надання первинних даних і визначення сценарію.
""")


def evidence_and_assets(summary: dict) -> None:
    records = [
        ("2.1", "Три макети і критерій argmax/пороги", "02_research/research_problem_and_math.md", "ml/features.py; ml/policy.py", "source inspection; pytest", "derived", "λC не реалізовано", "PASS"),
        ("2.2", "360 синтетичних рядків, 120 псевдоучасників; жодних реальних міток", "02_research/data_inventory.csv", "data/sample_synthetic/feature_rows.csv", "scripts/generate_synthetic_data.py; scripts/handoff_reproducibility.py", "synthetic", WARN, "PASS"),
        ("2.3", "10 predecision модельних ознак", "02_research/feature_dictionary.csv", "ml/features.py; results/feature_dictionary.csv", "source inspection; tests/test_research.py", "derived", "Runtime розбіжність для prior_undo_rate/time_of_day_bin", "PASS"),
        ("2.4", "П'ять стратегій на спільному синтетичному test 72", "02_research/models_comparison.csv", "results/synthetic/models_comparison.csv; results/split_manifest.json", "scripts/handoff_reproducibility.py", "synthetic", "Не переносити на людей", "PASS"),
        ("2.4", "Матриці помилок усіх стратегій", "02_research/confusion_matrices.csv", "results/synthetic/evaluation_report.json", "scripts/export_thesis_handoff.py", "synthetic", "Ті самі 72 test rows", "PASS"),
        ("2.5", "Локальна пропозиція, reject, accept, undo", "02_research/policy_trace_synthetic.json", "scripts/handoff_capture.py; backend/app.py", "python scripts/handoff_capture.py", "synthetic", "Автоматизовані дії, не людина", "PASS"),
        ("2.7", "Ablation 64/45/45 рекомендацій; 8/27/27 fallback", "02_research/ablation_results.csv", "results/synthetic/ablation.csv", "scripts/handoff_reproducibility.py", "synthetic", "Replay; не UX effect", "PASS"),
        ("3.1–3.6", "Архітектура, шість схем, ORM, REST", "03_design/api_openapi.json", "backend/app.py; docs/diagrams", "backend.app:app.openapi(); Base.metadata", "derived", "Без міграцій", "PASS"),
        ("4.1–4.4", "Працюючі UI стани і API", "04_implementation/screenshots_index.md", "frontend/src/App.tsx; backend/app.py", "python scripts/handoff_capture.py", "screenshot", "Тестовий синтетичний сценарій", "PASS"),
        ("4.5", "11 pytest та 1 Vitest пройшли", "05_tests/test_report.md", "05_tests/raw_logs/pytest.stdout.txt; 05_tests/raw_logs/frontend_unit.stdout.txt", "python -m pytest -q; npm test", "derived", "1 стороннє DeprecationWarning", "PASS"),
        ("4.6", "Локальний p50/p95 inference і health", "05_tests/performance_benchmarks.csv", "05_tests/raw_logs/performance_benchmark.stdout.txt", "python scripts/handoff_benchmark.py", "derived", "In-process; synthetic ML input", "PASS"),
        ("4.7", "Реальне UX дослідження", "06_real_ux/README_ACTUAL_STATUS.md", "data/real; results/real", "repository inventory", "unknown", "REAL_UX_NOT_CONDUCTED", "BLOCKED"),
        ("5.1–5.5", "Фактичні години і витрати", "07_economics/actual_worklog_or_unknown.md", "git rev-parse --verify HEAD; repository inventory", "source inspection", "unknown", "ACTUAL_HOURS_UNKNOWN", "BLOCKED"),
    ]
    for figure in sorted((H / "02_research/figures").glob("*")):
        rel = figure.relative_to(H).as_posix()
        records.append(("2.7", f"Рисунок {figure.name}", rel, f"results/synthetic/{figure.name}",
                        "scripts/research_demo.py; scripts/handoff_reproducibility.py", "synthetic", WARN, "PASS"))
    for diagram in sorted((H / "03_design/diagrams").glob("*.svg")):
        rel = diagram.relative_to(H).as_posix()
        records.append(("3.1–3.6", f"Діаграма {diagram.stem}", rel, f"docs/diagrams/{diagram.stem}.mmd",
                        "source diagram render; source inspection", "derived", "Схема поточного прототипу", "PASS"))
    for screenshot in sorted((H / "04_implementation/screenshots").glob("*.png")):
        rel = screenshot.relative_to(H).as_posix()
        records.append(("4.3", f"Скриншот {screenshot.name}", rel, "scripts/handoff_capture.py; frontend/src/App.tsx",
                        "python scripts/handoff_capture.py", "screenshot", "Автоматизований synthetic сценарій; не UX trial", "PASS"))
    cols = ["section", "claim_or_metric", "artifact_path", "raw_source_path", "calculation_or_command", "source_kind", "caveat", "status"]
    write_csv("EVIDENCE_MAP.csv", [dict(zip(cols, row)) for row in records], cols)
    (H / "08_thesis_assets").mkdir(parents=True, exist_ok=True)
    shutil.copy2(H / "EVIDENCE_MAP.csv", H / "08_thesis_assets/CLAIM_EVIDENCE_REGISTER.csv")
    ORIGINS["08_thesis_assets/CLAIM_EVIDENCE_REGISTER.csv"] = "EVIDENCE_MAP.csv"
    for src in ("THESIS_TABLES_UA.md", "THESIS_FIGURES_UA.md", "EXPERIMENT_METHODS_UA.md", "LIMITATIONS_UA.md", "ARTIFACT_MANIFEST.json"):
        copy(f"results/{src}", f"08_thesis_assets/original_results/{src}")
    comparisons = csv_rows(H / "02_research/models_comparison.csv")
    tab = ["# Таблиці для розділів 2–5", "", WARN, "", "## Розділ 2: спільний test (72 синтетичних рядки)", "", "| Стратегія | Accuracy | Macro-F1 | LogLoss |", "|---|---:|---:|---:|"]
    for r in comparisons:
        tab.append(f"| {r['model']} | {float(r['accuracy']):.3f} | {float(r['macro_f1']):.3f} | {float(r['logloss']):.3f} |" if r["logloss"] else f"| {r['model']} | {float(r['accuracy']):.3f} | {float(r['macro_f1']):.3f} | N/A |")
    tab += ["", "Першоджерело: `../02_research/models_comparison.csv`; відтворення: `scripts/handoff_reproducibility.py`. Це не зміна UX.", "", "## Розділ 3", "", "Таблиця модулів у `../04_implementation/code_modules_for_appendix.md`; ORM схему в `../03_design/db_schema.json`; API у `../03_design/api_openapi.json`.", "", "## Розділ 4", "", "Таблиця тестів у `../05_tests/commands_and_status.csv`, швидкодії — `../05_tests/performance_benchmarks.csv`. Реальна UX таблиця: `NOT_AVAILABLE`.", "", "## Розділ 5", "", "Фактичні години та витрати: `NOT_AVAILABLE`; припущення в `../07_economics/economic_assumptions.md`."]
    write("08_thesis_assets/TABLES_FOR_CHAPTERS_UA.md", "\n".join(tab))
    figures = ["# Рисунки для розділів", "", "Розділ 2: графіки `../02_research/figures/` із видимим маркером синтетичного походження; перші: `class_distribution`, `feature_distribution`, `models_comparison`, `ablation` та confusion matrices. Немає графіків реальних людей.", "", "Розділ 3: редаговані діаграми і SVG/PNG у `../03_design/diagrams/`: `system_context`, `use_cases`, `component`, `sequence_recommendation`, `activity_hybrid_policy`, `erd`.", "", "Розділ 4: справжні браузерні скриншоти 01–10 у `../04_implementation/screenshots/`, підписи — `screenshots_index.md`. Дані і дії тестові.", "", "Історичний файл з пропозиціями підписів: `original_results/THESIS_FIGURES_UA.md`; перед публікацією зіставити кожен підпис із `EVIDENCE_MAP.csv`."]
    write("08_thesis_assets/FIGURES_FOR_CHAPTERS_UA.md", "\n".join(figures))
    presentation = [
        ("03_design/diagrams/system_context.svg", "Контекст прототипу"),
        ("03_design/diagrams/component.svg", "Компоненти React/FastAPI/ML/БД"),
        ("03_design/diagrams/sequence_recommendation.svg", "Шлях події до пропозиції"),
        ("03_design/diagrams/activity_hybrid_policy.svg", "Порогова гібридна політика"),
        ("02_research/figures/class_distribution.svg", "Розподіл синтетичних міток"),
        ("02_research/figures/models_comparison.svg", "Offline порівняння на синтетичному test"),
        ("02_research/figures/ablation.svg", "Синтетична абляція"),
        ("04_implementation/screenshots/01_static_standard.png", "Стандартний UI, локальний тест"),
        ("04_implementation/screenshots/06_rule_proposal_preview_test.png", "Підтверджувана рекомендація, локальний тест"),
        ("04_implementation/screenshots/09_undo_standard_test.png", "Undo, локальний тест"),
    ]
    write("08_thesis_assets/PRESENTATION_ASSETS_UA.md", "# Рекомендовані власні матеріали для слайдів\n\n" + "\n".join(f"{i}. `{path}` — {caption}; джерело й обмеження в `../EVIDENCE_MAP.csv`." for i, (path, caption) in enumerate(presentation, 1)))
    write("08_thesis_assets/APPENDICES_INDEX_UA.md", """# Покажчик додатків

А — вихідний код і конфігурації (`../source_snapshot.zip`); Б — схема БД та фактичний OpenAPI (`../03_design/`); В — протокол і машинні synthetic результати (`../02_research/`); Г — діаграми та UI скриншоти (`../03_design/diagrams/`, `../04_implementation/screenshots/`); Д — виконані перевірки, повні логи, середовище (`../05_tests/`); Е — шаблони майбутнього реального UX (`../06_real_ux/templates/`). У додатках В–Г явно зазначати синтетичний/автоматизований характер.
""")
    write("08_thesis_assets/NEW_REFERENCES_TO_VERIFY.md", """# Нові джерела для рукопису

Бібліографічні [1]–[30] з розділу 1 зберігаються. Нових записів [31]+ не вигадано: вони потребують фактичного першого цитування в рукописі, повної перевірки метаданих і відповідності методичці. Документація Python/FastAPI/React, використана для інженерії, автоматично не переноситься в бібліографію. Наявний `docs/BIBLIOGRAPHY_HANDOFF.md` збережено у source snapshot; автор має звірити кінцевий текст і список.
""")


def overview_and_repro() -> None:
    sections = [
        ("2.1", "формалізація", "02_research/research_problem_and_math.md", "так", "λC не реалізовано", "READY"),
        ("2.2", "дані й мітки", "02_research/data_inventory.csv", "так", "лише synthetic", "PARTIAL"),
        ("2.3", "ознаки", "02_research/feature_dictionary.csv", "так", "runtime/offline розбіжність", "READY"),
        ("2.4", "порівняльні моделі", "02_research/models_comparison.csv", "так", "немає реальної оцінки", "PARTIAL"),
        ("2.5", "гібридна політика", "02_research/hybrid_algorithm_and_pseudocode.md", "так", "немає реального прийняття", "READY"),
        ("2.6", "методика", "02_research/split_protocol.md", "так", "немає time holdout/CI", "PARTIAL"),
        ("2.7", "synthetic результати", "02_research/ablation_results.csv", "так", "не доводить UX", "PARTIAL"),
        ("3.1", "вимоги", "03_design/requirements.md", "код", "немає повного WCAG аудиту", "PARTIAL"),
        ("3.2", "модулі", "03_design/modules_and_dataflows.md", "код", "—", "READY"),
        ("3.3", "сценарії та компоненти", "03_design/diagrams/use_cases.svg", "код", "—", "READY"),
        ("3.4", "алгоритм і sequence", "03_design/diagrams/sequence_recommendation.svg", "код", "—", "READY"),
        ("3.5", "модель БД", "03_design/db_schema.json", "код", "немає міграцій", "PARTIAL"),
        ("3.6", "REST API", "03_design/api_openapi.json", "так", "локальний прототип", "READY"),
        ("4.1", "стек", "01_project/stack_and_versions.md", "так", "—", "READY"),
        ("4.2", "модулі коду", "04_implementation/code_modules_for_appendix.md", "код", "—", "READY"),
        ("4.3", "UI", "04_implementation/screenshots_index.md", "так", "тестові сценарії", "READY"),
        ("4.4", "backend та API", "03_design/api_openapi.json", "так", "—", "READY"),
        ("4.5", "тести", "05_tests/test_report.md", "так", "ручна доступність відсутня", "PARTIAL"),
        ("4.6", "швидкодія", "05_tests/performance_benchmarks.csv", "так", "тільки локально", "PARTIAL"),
        ("4.7", "реальний UX", "06_real_ux/README_ACTUAL_STATUS.md", "ні", "REAL_UX_NOT_CONDUCTED", "BLOCKED"),
        ("5.1", "ресурси", "07_economics/actual_resources.md", "частково", "немає вартості обладнання", "PARTIAL"),
        ("5.2", "праця", "07_economics/actual_worklog_or_unknown.md", "ні", "ACTUAL_HOURS_UNKNOWN", "BLOCKED"),
        ("5.3", "витрати", "07_economics/economic_assumptions.md", "ні", "немає рахунків/тарифів", "BLOCKED"),
        ("5.4", "економічний розрахунок", "07_economics/economic_assumptions.md", "ні", "потрібні фактичні або обґрунтовані вводи", "BLOCKED"),
        ("5.5", "висновки", "07_economics/actual_worklog_or_unknown.md", "ні", "недостатньо доказів", "BLOCKED"),
    ]
    lines = ["# Готовність за підрозділами", "", "READY означає готовність описати **фактично реалізований прототип** з відповідними обмеженнями; PARTIAL — текст потребує суттєвого обмеження; BLOCKED — немає первинних даних.", "", "| Пункт | Матеріал | Файл | Запуск/код | Пропуски | Текст |", "|---|---|---|---|---|---|"]
    lines += ["| " + " | ".join(row) + " |" for row in sections]
    lines += ["", "**Розділ 2: PARTIAL** — повний опис synthetic методики можливий, емпіричні твердження про людей заблоковані.", "**Розділ 3: READY** для архітектури наявного прототипу, з вказівкою на відсутність міграцій.", "**Розділ 4: PARTIAL** — реалізація, перевірки й локальна швидкодія підтверджені; 4.7 заблоковано.", "**Розділ 5: BLOCKED** для фактичного економічного висновку через відсутність worklog та кошторисних джерел."]
    write("STATUS_BY_SECTION.md", "\n".join(lines))
    write("PLAN_VS_IMPLEMENTATION.md", """# План і фактичний код

| Планувалося | Реалізовано | Різниця | Наслідок для тексту |
|---|---|---|---|
| Мінімізувати втрати з `λ·C(layout,current)` (`docs/MATH_MODEL.md`) | `argmax p(layout|x)` і окремі пороги (`ml/policy.py`) | Штраф у функції вибору відсутній | Не заявляти оптимізацію з λ |
| Єдина схема ознак offline/runtime | Runtime `prior_undo_rate=0`, `time_of_day_bin=day` (`backend/app.py`) | Частина runtime ознак відрізняється | Offline метрики не є оцінкою runtime якості |
| Реальні preferred_layout та добровольці | Тільки synthetic generator і порожні шаблони | Реального дослідження немає | 4.7 та UX висновки блоковані |
| Time split/CI і незалежна UX валідація | Group split за participant_id і один test набір | Немає часової чутливості/CI | Зазначити обмеження 2.6–2.7 |
| Міграційна схема БД | ORM `create_all` | Міграцій немає | Описати як прототипну схему |
| Повний WCAG 2.2 AA аудит | Автоматизовані перевірки і клавіатурні сценарії | Повного ручного аудиту немає | Не писати, що AA відповідність доведена |
| Економічний розрахунок фактичних витрат | Лише snapshot ресурсів | Worklog і рахунків немає | Розділ 5 залишається умовним |
""")
    write("CHANGES_MADE.md", """# Зміни під час передачі

Логіка frontend, backend і ML не змінювалася; попередні `results/` не видалялися. Додано п'ять службових скриптів: `scripts/handoff_audit.py` (запуск команд, логи/статуси), `scripts/handoff_reproducibility.py` (повторна synthetic оцінка в тимчасовій папці і порівняння), `scripts/handoff_capture.py` (справжні скриншоти у Chrome з одноразовою БД), `scripts/handoff_benchmark.py` (30 локальних замірів) та цей `scripts/export_thesis_handoff.py` (структура, джерела, хеші, архів). Перший контрольний запуск `handoff_reproducibility.py` FAIL через відсутній project root у `sys.path`; додано імпортний шлях, наступний запуск PASS. Перший `handoff_audit.py` FAIL через нестворений `01_project/`; додано `mkdir`, повторний запуск PASS. Початкові помилки зафіксовано в `05_tests/commands_attempt1.csv` і `raw_logs/*attempt1*`. Дві невдалі спроби експортера описано в `05_tests/export_attempts.md`. Окремий capture запускав і видалив тимчасову SQLite. Джерело всіх підсумків — фактичні репозиторій і логи.
""")
    write("README_FIRST_UA.md", """# Комплект доказів для магістерської

Це аудит **наявного** працюючого прототипу, а не нова реалізація. Читайте спочатку `STATUS_BY_SECTION.md`, `EVIDENCE_MAP.csv`, `PLAN_VS_IMPLEMENTATION.md`, потім машинні дані в `02_research/`, архітектуру `03_design/`, скриншоти `04_implementation/`, логи `05_tests/`. Відтворювані джерела в `source_snapshot.zip`; повний список і SHA-256 у `MANIFEST.json`.

**СИНТЕТИЧНІ ДАНІ — НЕ Є ОЦІНКОЮ РЕАЛЬНИХ КОРИСТУВАЧІВ.** Реальне UX дослідження не проводилося (`REAL_UX_NOT_CONDUCTED`), фактичні години роботи невідомі (`ACTUAL_HOURS_UNKNOWN`). У розділі 2 можна описати метод і offline synthetic перевірку; у розділі 3 фактичну архітектуру; у розділі 4 код, тести й локальні заміри. Висновки про людську ефективність та економічний ефект потребують авторських первинних даних.

Оригінальні `results/THESIS_TABLES_UA.md`, `THESIS_FIGURES_UA.md`, `EXPERIMENT_METHODS_UA.md`, `LIMITATIONS_UA.md`, `ARTIFACT_MANIFEST.json` збережено в `08_thesis_assets/original_results/`. Усі згенеровані синтетичні графіки несуть видимий дисклеймер; машинні CSV/JSON мають маркери походження або супровідний опис. Діаграми і скриншоти додані як готові файли.
""")
    write("09_reproducibility/build_and_run_instructions.md", """# Відтворення

Розпакувати `source_snapshot.zip`; встановити сумісний Python 3.12, `pip install -r requirements.txt`, Node/npm, `cd frontend && npm ci`. У корені: `python scripts/research_demo.py` (synthetic), `python -m pytest -q`, `python scripts/check_deliverables.py`, `python scripts/check_deliverables.py --strict`, `cd frontend && npm run typecheck && npm test && npm run build`, `python tests/e2e_browser.py` за наявності Chrome. Docker: `docker compose -f docker-compose.example.yml up -d --build` після встановлення локальної змінної `UI_ML_DB_PASSWORD`; production секрети не передані. Деталі — `../01_project/commands_reproduction.md` і зафіксовані логи в `../05_tests/`.

Для перевірки комплекту: `python 09_reproducibility/export_scripts/check_handoff.py thesis_handoff`. Для повного повторного експорту з репозиторію: `python scripts/handoff_audit.py`, `python scripts/handoff_capture.py`, `python scripts/handoff_benchmark.py`, `python scripts/export_thesis_handoff.py`. Усі тестові події синтетичні.
""")
    write("09_reproducibility/reproducibility_check.md", """# Перевірка відтворюваності

`synthetic_repro` вдруге PASS: команда створила новий тимчасовий каталог, заново обчислила synthetic split, metric CSV і confusion matrices та порівняла їх із збереженими; latency виключена через природну мінливість. Test IDs не перетинаються з train/validation. Seed і пакети — `../02_research/split_manifest.json` і `../01_project/run_environment.json`; stdout/stderr — `../05_tests/raw_logs/synthetic_repro.*`. Перша невдала спроба збережена. Маніфест SHA-256 дозволяє перевірити кожен файл передачі. Відтворюваність на іншій ОС не тестувалася.
""")
    write("05_tests/export_attempts.md", """# Невдалі спроби службового експортера

Ці діагностичні повідомлення переписані з фактичного виводу інструмента; окремого сирого stdout/stderr із тих коротких інтерактивних викликів немає, timestamp не зафіксовано. Для наукових результатів вони значення не мають.

1. `python scripts/export_thesis_handoff.py` → exit 1, `ModuleNotFoundError: No module named 'backend'` при імпорті OpenAPI. Виправлено додаванням project root до `sys.path`.
2. Повтор → exit 1, `FileNotFoundError` при копіюванні `EVIDENCE_MAP.csv` у ще нестворений `08_thesis_assets/`. Виправлено `mkdir`.
3. Третій запуск → exit 0; структуру і SHA-256 підтвердив `check_handoff.py`.
""")
    if SOURCE_REQUEST.is_file():
        with zipfile.ZipFile(SOURCE_REQUEST) as archive:
            checker = next((n for n in archive.namelist() if n.endswith("check_handoff.py")), None)
            if checker:
                write("09_reproducibility/export_scripts/check_handoff.py", archive.read(checker).decode("utf-8"), "user-provided UI_ML_Handoff_Request.zip:check_handoff.py")
    for script in ("handoff_audit.py", "handoff_capture.py", "handoff_benchmark.py", "handoff_reproducibility.py", "export_thesis_handoff.py"):
        copy(f"scripts/{script}", f"09_reproducibility/export_scripts/{script}")


def manifest_and_package() -> None:
    def kind(path: str) -> str:
        if path.startswith("04_implementation/screenshots/"):
            return "screenshot"
        if path.startswith("02_research/") and ("real" not in path):
            return "synthetic" if Path(path).suffix in {".csv", ".json", ".jsonl", ".png", ".svg"} else "documentation"
        if path.startswith("05_tests/") or path.endswith("source_snapshot.zip") or path.endswith("api_openapi.json"):
            return "derived"
        if path.startswith("06_real_ux/") and Path(path).suffix in {".csv", ".json"}:
            return "unknown"
        return "documentation"
    records = []
    for path in sorted(H.rglob("*")):
        if not path.is_file() or path.name == "MANIFEST.json":
            continue
        rel = path.relative_to(H).as_posix()
        records.append({"path": rel, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "source_kind": kind(rel),
                        "origin": ORIGINS.get(rel, "existing audited output or executed capture/log"),
                        "command": "python scripts/export_thesis_handoff.py" if rel in ORIGINS else "python scripts/handoff_audit.py / handoff_capture.py / handoff_benchmark.py",
                        "notes": WARN if kind(rel) == "synthetic" else ("automated local test; no participant" if kind(rel) == "screenshot" else "")})
    write("MANIFEST.json", records)
    archive_path = ROOT / "THESIS_HANDOFF.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=8) as archive:
        for path in sorted(H.rglob("*")):
            if path.is_file():
                archive.write(path, (Path("thesis_handoff") / path.relative_to(H)).as_posix())
    print(json.dumps({"files": len(records), "archive_bytes": archive_path.stat().st_size, "source_bytes": (H / "source_snapshot.zip").stat().st_size}, ensure_ascii=False))


def main() -> None:
    summary, split, rows = inspect_data()
    runtime = json.loads((H / "01_project/run_environment.json").read_text(encoding="utf-8"))
    project_files(runtime)
    research_files(summary, split, rows)
    design_files()
    implementation_files()
    test_files()
    real_ux_files()
    economic_files(runtime)
    evidence_and_assets(summary)
    overview_and_repro()
    source_archive()
    manifest_and_package()


if __name__ == "__main__":
    main()

