"""Extended burn chart (Excel sheet «Диаграмма»)."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from .model import SprintForecast


def _sprint_label(sprint) -> str:
    if sprint.sprint_number == 0:
        return "Старт"
    if sprint.end is not None:
        return sprint.end.strftime("%d.%m")
    return str(sprint.sprint_number)


def plot_burn_chart(
    forecast: SprintForecast,
    *,
    output: str | Path = "burn_chart.png",
    show: bool = False,
) -> Path:
    """
    Draw the extended burn chart:
    - bars: Вверх (remaining of initial backlog), Низ (−cumulative added)
    - lines: тренд остатка, тренд добавленного, факт «Осталось работы»
    """
    output = Path(output)
    labels = [_sprint_label(s) for s in forecast.sprints]
    x = np.arange(len(forecast.sprints))

    upper = [s.upper if s.upper is not None else np.nan for s in forecast.sprints]
    lower = [s.lower if s.lower is not None else np.nan for s in forecast.sprints]
    remaining = [
        s.remaining if s.remaining is not None else np.nan for s in forecast.sprints
    ]
    trend_rem = [
        s.trend_remaining if s.trend_remaining is not None else np.nan
        for s in forecast.sprints
    ]
    trend_add = [
        s.trend_added if s.trend_added is not None else np.nan for s in forecast.sprints
    ]

    fig, ax = plt.subplots(figsize=(12, 6))

    width = 0.65
    ax.bar(
        x,
        upper,
        width=width,
        color="#5B8FF9",
        label="Вверх",
        zorder=2,
    )
    ax.bar(
        x,
        lower,
        width=width,
        color="#F6BD16",
        label="Низ",
        zorder=2,
    )

    ax.plot(
        x,
        remaining,
        color="#5AD8A6",
        marker="o",
        linewidth=2,
        label="Осталось работы",
        zorder=3,
    )
    ax.plot(
        x,
        trend_rem,
        color="#E86452",
        linestyle="--",
        linewidth=2,
        label="Линия тренда",
        zorder=3,
    )
    ax.plot(
        x,
        trend_add,
        color="#945FB9",
        linestyle="--",
        linewidth=2,
        label="Тренд добавленного",
        zorder=3,
    )

    # Mark current sprint
    ax.axvline(
        forecast.current_sprint,
        color="#666666",
        linestyle=":",
        linewidth=1.2,
        label=f"Текущий спринт ({forecast.current_sprint})",
        zorder=1,
    )
    ax.axhline(0, color="#333333", linewidth=0.8, zorder=1)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("Оценка (story points)")
    ax.set_title("Расширенная диаграмма выгорания")
    ax.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax.legend(loc="upper right", framealpha=0.92)

    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    if show:
        plt.show()
    plt.close(fig)
    return output
