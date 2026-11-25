# Методика відтворення

Команда: `make research-demo` або `powershell -File scripts/research-demo.ps1`. Seed: 20261103. Джерело: synthetic. Train/validation/test — неперетинні псевдонімні учасники 60/20/20. Ознаки обмежені колонками `ml.features.MODEL_FEATURES`; observed_until строго передує decision_at. Препроцесинг fit лише на train; два варіанти кожної ML-моделі обираються за validation Macro-F1; test оцінюється один раз. Статичний і правиловий baseline не мають LogLoss. Політика показує ймовірність явної переваги, а не очікуване поліпшення UX.

Сирі значення: `synthetic/models_comparison.csv`, `synthetic/ablation.csv`, `synthetic/evaluation_report.json`; параметри й версії: `config_snapshot.json`.
