# Статус реалізації — 03.11.2026

| Частина | Статус | Доказ / межа |
|---|---|---|
| Схеми й перевірка входу | PASS | `contracts/`; `python scripts/validate_input_bundle.py` |
| Synthetic ML pipeline, 5 стратегій | PASS | `results/synthetic/models_comparison.csv`; `make research-demo` / PowerShell еквівалент |
| Груповий split, predecision ознаки | PASS | `results/split_manifest.json`; `tests/test_research.py` |
| Політика з порогом, cooldown, confirm/undo | PASS | `ml/policy.py`; API/E2E тести |
| API, згода, видалення | PASS | `backend/app.py`; 11 Python тестів |
| Три макети, шість віджетів | PASS | React build; браузерні скриншоти |
| Frontend typecheck/unit/build | PASS | `results/test_results.json` |
| Браузерний E2E | PASS | `python tests/e2e_browser.py` |
| Docker build і локальний запуск | PASS | `docker compose up -d --build`; health 200 на порту 18000 |
| Аудит npm-залежностей | PASS | `npm audit`: 0 вразливостей на момент запуску |
| Сувора перевірка артефактів | PASS | `python scripts/check_deliverables.py --strict`: 28/28; жодної проблеми контракту |
| Реальні мітки/UX/SUS | BLOCKED | Добровільних перевірених даних не надано; `results/real/README.md` |
| Повний ручний аудит WCAG 2.2 AA | BLOCKED | Не проводився; автоматичні перевірки не замінюють аудит |

Історія фактично виконаних команд: `results/test_results.json` і `results/command_log.md`. Synthetic числа не слід переносити до висновків про людей.
