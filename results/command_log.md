# Журнал команд — 03.11.2026

1. `python -m pip install SQLAlchemy==2.0.44 xgboost==3.1.1` — успішно; XGBoost дійсно встановлено.
2. `powershell -ExecutionPolicy Bypass -File scripts/research-demo.ps1` — synthetic набір і результати створено за seed 20261103; після виправлення порядку класів у LogLoss команду повторено.
3. `python -m pytest -q` — 11 PASS; одне попередження з установленої dateutil.
4. `python scripts/validate_input_bundle.py` — PASS; 19 вхідних файлів, 360 synthetic рядків.
5. `python scripts/research_real.py` — MODEL_NOT_EVALUABLE; жодного real bundle не надано.
6. `npm run typecheck`, `npm test`, `npm run build` — PASS; 1 frontend unit test.
7. `npm audit --json` — 0 уразливостей після оновлення Vite/Vitest.
8. `python tests/e2e_browser.py` — PASS у headless Chrome; справжні скриншоти у `results/screenshots/`; тестову БД видалено після прогону.
9. `docker compose build`, `docker compose up -d --build` — PASS; PostgreSQL healthy, API `/health` 200, frontend 200. Для уникнення конфлікту з іншим локальним проєктом використано порти 18000 і 15173.
10. Mermaid CLI — 6 джерел `.mmd` експортовано у SVG і PNG.
11. `python scripts/check_deliverables.py --strict` — 28/28 обов'язкових файлів, жодної проблеми контракту.
12. `docker compose up -d --build` після створення `requirements-linux.lock` — чисте встановлення за lockfile і повторний успішний запуск; PostgreSQL не містить тестових учасників.

Час виконання та latency можуть залежати від хоста; synthetic офлайнові метрики зберігають відтворюваність за однаковими залежностями й seed.
