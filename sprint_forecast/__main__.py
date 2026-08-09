"""CLI: run forecast from Excel test data or a Jira epic."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from .excel_loader import load_excel_params, load_plan_from_excel
from .model import compute_forecast, forecast_to_dataframe
from .plot import plot_burn_chart


def _period_name(forecast, args: argparse.Namespace) -> str:
    if getattr(args, "period_name", None):
        return args.period_name
    return "неделя" if forecast.sprint_length_days == 7 else "спринт"


def _print_summary(forecast, args: argparse.Namespace | None = None) -> None:
    period = "период"
    if args is not None:
        period = _period_name(forecast, args)
    print("=== Сводка ===")
    print(f"Начальный объём работы: {forecast.initial_backlog_size}")
    print(f"Объём работы:           {forecast.backlog_size}")
    print(f"Длина периода:          {forecast.sprint_length_days} д ({period})")
    print(f"Дата отчёта:            {forecast.report_date}")
    print(f"Текущий {period}:       {forecast.current_sprint}")
    print(f"Остаток работы:         {forecast.remaining_work}")
    print(
        f"Велосити:               {forecast.velocity_mean:.4g} "
        f"(STD {forecast.velocity_std:.4g})"
    )
    print(
        f"Добавлясити:            {forecast.addlocity_mean:.4g} "
        f"(STD {forecast.addlocity_std:.4g})"
    )
    print()
    df = forecast_to_dataframe(forecast)
    # Show future probabilities more clearly
    future = df[df["n"] > 0][
        [
            "sprint",
            "start",
            "end",
            "n",
            "prob_finish_by",
            "prob_finish_by_freeze",
            "prob_this_iteration",
        ]
    ]
    if not future.empty:
        print(f"=== Вероятность успеть к {period} ===")
        for _, row in future.iterrows():
            p = row["prob_finish_by"]
            pf = row["prob_finish_by_freeze"]
            dp = row["prob_this_iteration"]
            dp_s = "—" if dp is None or (isinstance(dp, float) and dp != dp) else f"{dp:.4%}"
            pf_s = "—" if pf is None or (isinstance(pf, float) and pf != pf) else f"{pf:.4%}"
            print(
                f"{period.capitalize()} {int(row['sprint']):2d} (N={int(row['n']):2d}) "
                f"{row['end']}: P={p:.4%}  P|A=0={pf_s}  ΔP={dp_s}"
            )


def _maybe_plot(forecast, args: argparse.Namespace) -> None:
    if args.no_chart:
        return
    path = plot_burn_chart(
        forecast,
        output=args.chart,
        show=args.show_chart,
        period_name=_period_name(forecast, args),
        estimate_unit=getattr(args, "estimate_unit", "story points"),
        title=getattr(args, "chart_title", None),
    )
    print(f"\nГрафик сохранён: {path.resolve()}")


def cmd_excel(args: argparse.Namespace) -> int:
    path = Path(args.excel)
    items = load_plan_from_excel(path)
    params = load_excel_params(path)
    forecast = compute_forecast(
        items,
        first_sprint_start=params["first_sprint_start"],
        sprint_length_days=params["sprint_length_days"],
        sprint_count=args.sprint_count,
    )
    _print_summary(forecast, args)
    if args.json:
        payload = {
            "initial_backlog_size": forecast.initial_backlog_size,
            "backlog_size": forecast.backlog_size,
            "report_date": forecast.report_date.isoformat(),
            "current_sprint": forecast.current_sprint,
            "remaining_work": forecast.remaining_work,
            "velocity_mean": forecast.velocity_mean,
            "velocity_std": forecast.velocity_std,
            "addlocity_mean": forecast.addlocity_mean,
            "addlocity_std": forecast.addlocity_std,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    _maybe_plot(forecast, args)
    return 0


def cmd_jira(args: argparse.Namespace) -> int:
    from .jira_loader import load_epic_issues

    items = load_epic_issues(
        args.epic,
        estimate_field=args.estimate_field,
    )
    if not items:
        print("Нет задач с оценкой в эпике.")
        return 1

    first_sprint_start = date.fromisoformat(args.first_sprint_start)
    forecast = compute_forecast(
        items,
        first_sprint_start=first_sprint_start,
        sprint_length_days=args.sprint_length,
        sprint_count=args.sprint_count,
        report_date=date.fromisoformat(args.report_date) if args.report_date else None,
    )
    _print_summary(forecast, args)
    _maybe_plot(forecast, args)
    return 0


def _add_chart_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--chart",
        default="burn_chart.png",
        help="Куда сохранить график (по умолчанию burn_chart.png)",
    )
    parser.add_argument(
        "--no-chart",
        action="store_true",
        help="Не строить график",
    )
    parser.add_argument(
        "--show-chart",
        action="store_true",
        help="Показать окно matplotlib (если есть дисплей)",
    )
    parser.add_argument(
        "--period-name",
        default=None,
        help="Подпись периода на графике (неделя/спринт). По умолчанию: неделя при length=7",
    )
    parser.add_argument(
        "--estimate-unit",
        default="story points",
        help="Единица оценки на оси Y (например: story points, часы)",
    )
    parser.add_argument(
        "--chart-title",
        default=None,
        help="Заголовок графика",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sprint forecasting model (порт Excel sprint_planning.xlsx)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_excel = sub.add_parser("excel", help="Считать Plan из xlsx и посчитать прогноз")
    p_excel.add_argument(
        "--excel",
        default="sprint_planning.xlsx",
        help="Путь к Excel (по умолчанию sprint_planning.xlsx)",
    )
    p_excel.add_argument("--sprint-count", type=int, default=15)
    p_excel.add_argument("--json", action="store_true")
    _add_chart_args(p_excel)
    p_excel.set_defaults(func=cmd_excel)

    p_jira = sub.add_parser("jira", help="Загрузить задачи эпика из Jira и посчитать прогноз")
    p_jira.add_argument("epic", help="Ключ эпика, например PROJ-123")
    p_jira.add_argument(
        "--first-sprint-start",
        required=True,
        help="Дата старта первого спринта YYYY-MM-DD",
    )
    p_jira.add_argument(
        "--sprint-length",
        type=int,
        default=7,
        help="Длина периода в днях (7 = по неделям, 14 = по двухнедельным спринтам)",
    )
    p_jira.add_argument(
        "--sprint-count",
        type=int,
        default=20,
        help="Сколько периодов вперёд строить (для недель обычно 20–24)",
    )
    p_jira.add_argument("--report-date", default=None, help="YYYY-MM-DD")
    p_jira.add_argument(
        "--estimate-field",
        default="customfield_10016",
        help="Jira custom field id для Story Points",
    )
    _add_chart_args(p_jira)
    p_jira.set_defaults(func=cmd_jira)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
