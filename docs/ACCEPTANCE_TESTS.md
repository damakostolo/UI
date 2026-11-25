# Acceptance tests та завершення робіт

## Експерименти

1. Same seed + input → детермінована модельна оцінка (у межах зазначеної чисельної толерантності).
2. Нульова кількість реальних учасників → немає `ux_summary.csv` зі сфабрикованими вимірами, `results/real/README.md` пояснює обмеження.
3. Dataset labels утворені в synthetic generator → `is_synthetic=true` у кожному рядку, у кожному графіку й у metadata.
4. Усі participant_id між train/val/test попарно неперетинні; відсутні future timestamps серед features. Test data не впливає на fitting, tuning або feature selection.
5. Лише коли є повні дані по кількох класах — macro-F1/logloss; за неможливості оцінки повернути структуровану помилку, а не NaN/0.
6. Модель з невпевненою оцінкою або cold start → current/default layout без мовчазної адаптації.

## Приватність і API

7. `consent=false` → жоден клік не викликає `POST /events`; direct `POST /events` → 403 і 0 DB rows.
8. Відкликання consent → нові події не приймаються; видалення профілю очищає пов'язані події.
9. Payload із зайвим `email`, `text`, `url`, `ip` → 4xx schema validation; не логувати заборонені поля.
10. Зміна UI доступна лише через confirm/accept; reject/undo/disable working even if model unreachable.

## UI

11. Всі 3 layouts показують 6 віджетів/навігацію і дозволяють завершити однакові demo tasks.
12. Tab/Enter/Escape, focus visibility, semantic headings/landmarks; жодна автоадаптація під час active_task.
13. Звичайний статичний UI працює при недоступному model endpoint.
14. API server відповідає `/health`, запити відповідають узгодженим JSON schema.
15. У README є команди для Linux/macOS і Windows PowerShell, є `.env.example` без секретів.

## Документація та виходи

16. `python scripts/check_deliverables.py` перевіряє документовані артефакти; повідомляє відсутні, нічого не підробляє.
17. Реальні тести виконано і результати записано `results/test_results.json`.
18. `results/ARTIFACT_MANIFEST.json` містить походження кожного результату, `is_synthetic` і SHA256. Скриншоти показують реальний запущений UI, а не макети.
19. Усі таблиці/рисунки розділу 2 мають відповідний CSV/JSON та скрипт генерації.
20. `results/STATUS.md` перераховує PASS/FAIL/BLOCKED з поясненнями та наступними кроками.
