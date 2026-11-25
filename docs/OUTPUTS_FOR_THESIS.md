# Контракт вихідних даних та відповідність підрозділам магістерської

Уся звітність — українською. **Звіти не є текстом дисертації:** таблиці й числа має можна перевірити за збереженими CSV/JSON та кодом.

| Підрозділ | Що необхідно з програми | Обов'язкові вихідні файли |
|---|---|---|
| 2.1 Формалізація | чіткі змінні, класи, функція вибору, обмеження | `results/EXPERIMENT_METHODS_UA.md`, `docs/MATH_MODEL.md` |
| 2.2 Набір даних | provenance, schema, consent, counts, класовий склад | `results/synthetic/dataset_card.md`, `dataset_summary.json`, `class_distribution.png` (+ `results/real` за наявності даних) |
| 2.3 Ознаки | перелік і формули ознак, predecision cutoff, missing-value policy | `results/feature_dictionary.csv`, `results/split_manifest.json` |
| 2.4 Алгоритми | static, rule, LR, RF, XGB (або blocker) з конфігурацією | `results/synthetic/models_comparison.csv`, `models_comparison.png`, `results/config_snapshot.json` |
| 2.5 Hybrid | threshold/gain/cooldown/accept/reject/undo, блок-схема | `docs/diagrams/activity_hybrid_policy.mmd`, `results/synthetic/policy_metrics.csv` |
| 2.6 Навчання | group split, train/val/test N, параметри, без leakage, repeatability | `results/split_manifest.json`, `results/synthetic/evaluation_report.json`, `results/synthetic/confusion_matrix.png` |
| 2.7 Експеримент | macro-F1 etc, ablation, errors & limits | `results/synthetic/ablation.csv`, `ablation.png`, `results/LIMITATIONS_UA.md` |
| 3.* Проєктування | ERD, component, usecase, sequence, API and schema | `docs/diagrams/*.mmd`, `docs/API.md` |
| 4.1–4.5 Програма | README, launch, code, tests, build, UI screenshots | `results/STATUS.md`, `results/test_results.json`, `results/screenshots/*.png` |
| 4.6 UX | реальні добровільні tasks, controls, N, duration, success, clicks | `results/real/ux_trials.csv`, `ux_summary.csv`, `ux_comparison.png` **лише якщо є real data** |
| 4.7 Практичне застосування | latency, fallback/coverage, limitations | `results/synthetic/system_benchmark.json`, `results/LIMITATIONS_UA.md` |

## Файли, які повинні існувати незалежно від реальних даних

- `results/STATUS.md`: матриця виконано/не виконано/blocked із командами й логами.
- `results/ARTIFACT_MANIFEST.json`: файли з роллю, походженням, synthetic flag, шляхом та SHA-256.
- `results/THESIS_TABLES_UA.md`: готові **посилання на результати**, заголовки таблиць 2.1–2.6, але лише фактично обчислені значення.
- `results/THESIS_FIGURES_UA.md`: перелік згенерованих ілюстрацій, пояснення осей, походження, підписи українською.
- `results/EXPERIMENT_METHODS_UA.md`: версії, команди, feature selection, split, metrics, методика.
- `results/LIMITATIONS_UA.md`: самокритична оцінка, відсутні реальні дані, погрози валідності, невідомі ефекти UX.
- `results/feature_dictionary.csv`: назва; опис; одиниця; момент доступності; null policy.
- `results/split_manifest.json`: seed; train_ids; validation_ids; test_ids (псевдонімні); disjoint=true; class_counts; cutoffs.
- `results/config_snapshot.json`: версії середовища, моделі, параметри, геш даних, seed.
- `results/test_results.json`: реальні виконані команди та результати; blocked не називати PASS.

## Назви зображень і формат

PNG 180–300 dpi, SVG за можливості; однакові осі й підписи, читаються при вставленні в документ A4. Назва рисунка українською. На графіках synthetic даних — помітне маркування **«СИНТЕТИЧНІ ДАНІ — НЕ Є ОЦІНКОЮ РЕАЛЬНИХ КОРИСТУВАЧІВ»**; не покладатися на ім'я файлу.

## Дані, що не можуть бути створені агентом без участі людей

Реальний `N`, результати користувацького тестування, анкети SUS, висновки про зменшення часу, етичне погодження або якість/унікальність тексту. Без учасників залиш `results/real/README.md` з точною процедурою збору замість статистики.
