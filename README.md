# sprint-forecasting-model

Python-порт расчётов из `sprint_planning.xlsx` (листы Plan / Formulas): burn-up/burn-down, велосити, добавлясити и вероятность успеть бэклог за N спринтов.

## Установка

```bash
pip install -r requirements.txt
```

## Тестовые данные (Excel)

По умолчанию берётся `sprint_planning.xlsx` из корня репозитория:

```bash
python3 -m sprint_forecast excel
python3 -m sprint_forecast excel --json
```

Проверка, что результат совпадает с кэшированными значениями Excel:

```bash
python3 -m pytest tests/test_against_excel.py -v
```

## Jira (эпик)

Когда будут доступы, можно грузить задачи эпика:

```bash
export JIRA_SERVER=https://your-domain.atlassian.net
export JIRA_EMAIL=you@example.com
export JIRA_API_TOKEN=...

pip install jira
python3 -m sprint_forecast jira PROJ-123 --first-sprint-start 2020-05-11
```

Story Points читаются из custom field (`--estimate-field`, по умолчанию `customfield_10016`).

## Что считается

| Показатель | Логика Excel |
|---|---|
| Начальный объём | сумма оценок с `created <` старт 1-го спринта |
| Объём работы | сумма всех оценок |
| Сделано / добавлено за спринт | `SUMIFS` по датам завершения / создания |
| Велосити | среднее и STDEV done за спринты 1–5 |
| Добавлясити | среднее added за 0–4, STDEV за 0–15 |
| Остаток | initial + Σadded − Σdone |
| P(успеть за N) | `1 - NORM.DIST(остаток, N·(V−A), √(N·(σA²+σV²)))` |
