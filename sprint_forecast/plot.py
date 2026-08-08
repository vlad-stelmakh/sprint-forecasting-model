"""Extended burn chart (Excel sheet «Диаграмма») with a proper probability panel."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import PercentFormatter

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
    Draw the extended burn chart + probabilities.

    Excel puts probabilities on a secondary axis mapped onto −75…75, so
    P=0 sits at the chart midline (looks «криво»). Here probabilities get
    their own panel with a real 0–100% scale.
    """
    output = Path(output)
    labels = [_sprint_label(s) for s in forecast.sprints]
    x = np.arange(len(forecast.sprints))

    upper = [s.upper if s.upper is not None else np.nan for s in forecast.sprints]
    lower = [s.lower if s.lower is not None else np.nan for s in forecast.sprints]
    trend_rem = [
        s.trend_remaining if s.trend_remaining is not None else np.nan
        for s in forecast.sprints
    ]
    trend_add = [
        s.trend_added if s.trend_added is not None else np.nan for s in forecast.sprints
    ]
    prob_finish = [
        s.prob_finish_by if s.prob_finish_by is not None else np.nan
        for s in forecast.sprints
    ]
    prob_iter = [
        s.prob_this_iteration if s.prob_this_iteration is not None else np.nan
        for s in forecast.sprints
    ]

    fig, (ax_burn, ax_prob) = plt.subplots(
        2,
        1,
        figsize=(12, 8),
        sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1.0], "hspace": 0.08},
    )

    width = 0.65
    ax_burn.bar(x, upper, width=width, color="#4A86E8", label="Вверх", zorder=2)
    ax_burn.bar(x, lower, width=width, color="#E06666", label="Низ", zorder=2)
    ax_burn.plot(
        x,
        trend_rem,
        color="#F1C232",
        linestyle="--",
        linewidth=2.2,
        label="Линия тренда",
        zorder=3,
    )
    ax_burn.plot(
        x,
        trend_add,
        color="#CC0000",
        linestyle="--",
        linewidth=2.0,
        label="Тренд добавленного",
        zorder=3,
    )
    ax_burn.axvline(
        forecast.current_sprint,
        color="#666666",
        linestyle=":",
        linewidth=1.2,
        label=f"Текущий спринт ({forecast.current_sprint})",
        zorder=1,
    )
    ax_burn.axhline(0, color="#333333", linewidth=0.8, zorder=1)

    # Symmetric y-limits around 0, like the Excel burn chart
    burn_vals = [v for v in upper + lower + trend_rem + trend_add if v == v]
    if burn_vals:
        span = max(abs(min(burn_vals)), abs(max(burn_vals)))
        span = max(span * 1.1, 1.0)
        ax_burn.set_ylim(-span, span)

    ax_burn.set_ylabel("Оценка (story points)")
    ax_burn.set_title("Расширенная диаграмма выгорания")
    ax_burn.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax_burn.legend(loc="upper right", framealpha=0.92, fontsize=9)

    # --- Probability panel (own scale — not a broken secondary axis) ---
    ax_prob.fill_between(
        x,
        prob_finish,
        color="#45818E",
        alpha=0.12,
        zorder=1,
    )
    ax_prob.plot(
        x,
        prob_finish,
        color="#45818E",
        marker="o",
        markersize=4,
        linewidth=2.2,
        label="Вероятность успеть все",
        zorder=3,
    )
    ax_prob.plot(
        x,
        prob_iter,
        color="#E69138",
        marker="s",
        markersize=4,
        linewidth=2.0,
        label="Вероятность сделать все в эту итерацию",
        zorder=3,
    )
    ax_prob.axvline(
        forecast.current_sprint,
        color="#666666",
        linestyle=":",
        linewidth=1.2,
        zorder=1,
    )
    ax_prob.set_ylim(0.0, 1.05)
    ax_prob.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax_prob.set_ylabel("Вероятность")
    ax_prob.set_xlabel("Дата завершения спринта")
    ax_prob.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax_prob.legend(loc="upper left", framealpha=0.92, fontsize=9)

    ax_prob.set_xticks(x)
    ax_prob.set_xticklabels(labels, rotation=45, ha="right")

    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    if show:
        plt.show()
    plt.close(fig)
    return output
