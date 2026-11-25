# Персоналізація інтерфейсу вебпанелі: дослідницький прототип

Локальна React/FastAPI панель із шістьма віджетами, трьома макетами та відтворюваним offline ML експериментом для магістерської роботи. **Synthetic результати перевіряють код і методику; реальних учасників або доведеного поліпшення UX у цьому репозиторії наразі немає.**

## Швидкий запуск

Потрібні Python 3.12, Node.js 22+ і npm. Docker потрібен лише для запуску з PostgreSQL. Python прямі залежності зафіксовано в `requirements.txt`, Linux-контейнер використовує повний `requirements-linux.lock`, frontend — `package-lock.json`.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd frontend
npm ci
cd ..
powershell -ExecutionPolicy Bypass -File scripts/research-demo.ps1
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --no-access-log
```

В іншому терміналі: `cd frontend; npm run dev`. Відкрийте `http://127.0.0.1:5173`. API: `http://127.0.0.1:8000/docs`. Статичний інтерфейс працює й без API. Дані за замовчуванням не збираються; після згоди створюється випадковий псевдонімний профіль. Токен зберігається в `sessionStorage` вкладки для відновлення після перезавантаження. Перед закриттям вкладки можна скопіювати код доступу; введіть його пізніше для експорту або видалення профілю. Зберігайте цей код приватно. Не використовуйте прототип для фактичного збору людей без погодженої процедури й версії згоди.

Linux/macOS: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && cd frontend && npm ci && cd .. && make research-demo`; сервери запускаються тими ж командами з `python3` і `npm`.

## Дослідницькі команди

- Synthetic demo: `make research-demo` або `powershell -File scripts/research-demo.ps1`. Результати: `results/synthetic/`; всі графіки мають помітний маркер синтетичного походження.
- Реальні дані: `make research-real` або `powershell -File scripts/research-real.ps1`. Без `--bundle` команда чесно повідомляє `MODEL_NOT_EVALUABLE` і не створює UX-метрик. Для перевіреного набору: `python scripts/research_real.py --bundle ШЛЯХ_ДО_ПАКЕТА`. Формат: `scripts/import_real_data.py`, `data/templates/`, `docs/EXPERIMENT_PROTOCOL.md`. Імпортер вимагає manifest походження та згоду кожного учасника.
- Перевірки: `python -m pytest -q`; `cd frontend && npm run typecheck && npm test && npm run build`; `python tests/e2e_browser.py` за наявності Chrome; `python scripts/check_deliverables.py --strict`.

## Архітектура

`frontend/` — React UI; `backend/` — FastAPI та SQLAlchemy; `ml/` — ознаки, group split, моделі й політика; `contracts/` — JSON Schema; `data/sample_synthetic/` — лише позначені тестові дані; `data/templates/` — порожні шаблони для добровільних вимірювань; `results/` — CSV, JSON, таблиці й графіки; `docs/diagrams/` — джерела діаграм. Події зберігаються локально до 30 днів; старі записи очищаються при надходженні нової події або командою `python scripts/cleanup_events.py`. `DELETE /profile/me` видаляє профіль і пов'язані записи. Відкликання згоди миттєво зупиняє новий збір, але раніше записані події треба видалити окремо кнопкою «Видалити профіль».

Без ML доступні статична панель, ручний вибір макета та шість однакових дій. Правилова стратегія працює з дозволених подій. ML модель, навчена на synthetic даних, може показувати рекомендації лише у явно позначеному DEMO режимі; вона не є перевіреною моделлю для людей. У всіх режимах зміна після рекомендації вимагає підтвердження, а скасування доступне окремо.

Для Docker: `docker compose up --build` після `make research-demo` / PowerShell еквівалента. Відкрийте `http://127.0.0.1:15173`; API доступний на `http://127.0.0.1:18000`. База PostgreSQL доступна лише контейнерам, інші порти проброшені тільки на localhost. Це локальна демонстрація, не production deployment.

Фактичні виконані перевірки, пропуски й обмеження: [results/STATUS.md](results/STATUS.md). Для розділів магістерської почніть із [results/THESIS_TABLES_UA.md](results/THESIS_TABLES_UA.md), [results/THESIS_FIGURES_UA.md](results/THESIS_FIGURES_UA.md) та [results/ARTIFACT_MANIFEST.json](results/ARTIFACT_MANIFEST.json).
