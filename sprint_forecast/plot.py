"""Extended burn chart (Excel sheet «Диаграмма») with a proper probability panel."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import PercentFormatter

from .model import SprintForecast


def _period_label(sprint, *, period_name: str) -> str:
    if sprint.sprint_number == 0:
        return "Старт"
    if sprint.end is not None:
        return sprint.end.strftime("%d.%m")
    return f"{period_name[0].upper()}{sprint.sprint_number}"


def _finite(values: list[float]) -> list[float]:
    return [v for v in values if v == v]  # NaN != NaN


def plot_burn_chart(
    forecast: SprintForecast,
    *,
    output: str | Path = "burn_chart.png",
    show: bool = False,
    period_name: str | None = None,
    estimate_unit: str = "story points",
    title: str | None = None,
) -> Path:
    """
    Draw the extended burn chart + probabilities.

    Excel puts probabilities on a secondary axis mapped onto −75…75, so
    P=0 sits at the chart midline (looks «криво»). Here probabilities get
    their own panel with a real 0–100% scale.

    Display improvements vs the Excel sheet:
    - clearer series names (остаток / добавлено)
    - legend outside the plot area
    - y-scale driven by history + near-term forecast (not a runaway far trend)
    - shaded historical region vs forecast
    - note when finish probability is effectively zero
    """
    output = Path(output)
    if period_name is None:
        period_name = "неделя" if forecast.sprint_length_days == 7 else "спринт"

    labels = [_period_label(s, period_name=period_name) for s in forecast.sprints]
    x = np.arange(len(forecast.sprints))
    current = forecast.current_sprint

    upper = [s.upper if s.upper is not None else np.nan for s in forecast.sprints]
    lower = [s.lower if s.lower is not None else np.nan for s in forecast.sprints]
    trend_rem = [
        s.trend_remaining if s.trend_remaining is not None else np.nan
        for s in forecast.sprints
    ]
    trend_add = [
        s.trend_added if s.trend_added is not None else np.nan for s in forecast.sprints
    ]
    # Sprint 0 in the Excel sheet stores remaining=0 as a placeholder — skip it
    # so the green "actual remaining" line does not fake a spike from 0.
    remaining = [
        (
            np.nan
            if s.sprint_number == 0 or s.remaining is None
            else s.remaining
        )
        for s in forecast.sprints
    ]
    prob_finish = [
        s.prob_finish_by if s.prob_finish_by is not None else np.nan
        for s in forecast.sprints
    ]
    prob_freeze = [
        s.prob_finish_by_freeze if s.prob_finish_by_freeze is not None else np.nan
        for s in forecast.sprints
    ]
    prob_iter = [
        s.prob_this_iteration if s.prob_this_iteration is not None else np.nan
        for s in forecast.sprints
    ]

    n_periods = len(forecast.sprints)
    # Wider canvas when there are many weekly buckets
    fig_w = max(12.0, min(18.0, 0.55 * n_periods + 4.0))
    fig, (ax_burn, ax_prob) = plt.subplots(
        2,
        1,
        figsize=(fig_w, 8.2),
        sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1.05], "hspace": 0.12},
    )
    # Leave room on the right for legends + bottom footnote
    fig.subplots_adjust(right=0.78, bottom=0.12, top=0.93, hspace=0.12)

    # Historical band (Старт .. current inclusive)
    ax_burn.axvspan(-0.5, current + 0.5, color="#E8EEF7", alpha=0.9, zorder=0)
    ax_prob.axvspan(-0.5, current + 0.5, color="#E8EEF7", alpha=0.9, zorder=0)

    width = 0.62 if n_periods <= 18 else 0.55
    ax_burn.bar(
        x,
        upper,
        width=width,
        color="#4A86E8",
        label="Остаток начального объёма",
        zorder=2,
    )
    ax_burn.bar(
        x,
        lower,
        width=width,
        color="#E06666",
        label="Накопленное добавленное (−)",
        zorder=2,
    )
    ax_burn.plot(
        x,
        remaining,
        color="#6AA84F",
        marker="o",
        markersize=3.5,
        linewidth=1.6,
        label="Фактический остаток",
        zorder=4,
    )
    ax_burn.plot(
        x,
        trend_rem,
        color="#F1C232",
        linestyle="--",
        linewidth=2.2,
        label="Тренд остатка",
        zorder=3,
    )
    ax_burn.plot(
        x,
        trend_add,
        color="#CC0000",
        linestyle="--",
        linewidth=2.0,
        label="Тренд добавленного (−)",
        zorder=3,
    )
    ax_burn.axvline(
        current,
        color="#666666",
        linestyle=":",
        linewidth=1.3,
        label=f"Сейчас ({period_name} {current})",
        zorder=1,
    )
    ax_burn.axhline(0, color="#333333", linewidth=0.8, zorder=1)

    # Y-limits: prefer history + near forecast, so far-future added trend
    # does not squash the bars to a thin strip.
    near = min(n_periods, current + 6)
    scale_vals = _finite(upper[: current + 1] + lower[: current + 1])
    scale_vals += _finite(remaining[: current + 1])
    scale_vals += _finite(trend_rem[:near] + trend_add[:near])
    if scale_vals:
        span = max(abs(min(scale_vals)), abs(max(scale_vals)))
        span = max(span * 1.15, 1.0)
        ax_burn.set_ylim(-span, span)

    unit = estimate_unit
    ax_burn.set_ylabel(f"Оценка ({unit})")
    ax_burn.set_title(title or "Расширенная диаграмма выгорания")
    ax_burn.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax_burn.legend(
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0.0,
        framealpha=0.95,
        fontsize=8.5,
    )

    # --- Probability panel ---
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
        label="P(успеть всё к дате)",
        zorder=3,
    )
    ax_prob.plot(
        x,
        prob_freeze,
        color="#6AA84F",
        marker="^",
        markersize=4,
        linewidth=2.2,
        linestyle="--",
        label="P при A=0 (заморозка scope)",
        zorder=3,
    )
    ax_prob.plot(
        x,
        prob_iter,
        color="#E69138",
        marker="s",
        markersize=4,
        linewidth=2.0,
        label=f"ΔP за {period_name}",
        zorder=3,
    )
    ax_prob.axvline(
        current,
        color="#666666",
        linestyle=":",
        linewidth=1.3,
        zorder=1,
    )

    finite_probs = _finite(prob_finish)
    finite_freeze = _finite(prob_freeze)
    max_p = max(finite_probs) if finite_probs else 0.0
    max_freeze = max(finite_freeze) if finite_freeze else 0.0
    if max_p < 0.01:
        reason = (
            f"P≈0%: добавление ({forecast.addlocity_mean:.1f}) "
            f"≥ велосити ({forecast.velocity_mean:.1f}) {unit}/{period_name}"
        )
        if max_freeze >= 0.01:
            reason += f"\nпри A=0: P до ~{max_freeze:.0%}"
        ax_prob.text(
            0.01,
            0.92,
            reason,
            transform=ax_prob.transAxes,
            fontsize=8.5,
            color="#990000",
            va="top",
            ha="left",
            bbox={
                "boxstyle": "round,pad=0.3",
                "facecolor": "#FFF2F2",
                "edgecolor": "#E06666",
                "linewidth": 0.6,
            },
            zorder=5,
        )
        ax_prob.set_ylim(0.0, 1.05)
    else:
        # Zoom if probabilities stay low but not flat-zero
        top = min(1.05, max(0.2, max(max_p, max_freeze) * 1.35))
        ax_prob.set_ylim(0.0, top)

    ax_prob.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax_prob.set_ylabel("Вероятность")
    ax_prob.set_xlabel(f"Дата завершения {period_name[:-1] if period_name.endswith('а') else period_name}и")
    # Fix awkward genitive: неделя→недели, спринт→спринта
    if period_name == "неделя":
        ax_prob.set_xlabel("Дата завершения недели")
    elif period_name == "спринт":
        ax_prob.set_xlabel("Дата завершения спринта")
    else:
        ax_prob.set_xlabel(f"Дата завершения ({period_name})")

    ax_prob.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)
    ax_prob.legend(
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0.0,
        framealpha=0.95,
        fontsize=8.5,
    )

    ax_prob.set_xticks(x)
    ax_prob.set_xticklabels(labels, rotation=45, ha="right")

    # Footnote with model snapshot
    fig.text(
        0.01,
        0.01,
        (
            f"Остаток={forecast.remaining_work:.1f} {unit} · "
            f"V={forecast.velocity_mean:.2g}±{forecast.velocity_std:.2g} · "
            f"A={forecast.addlocity_mean:.2g}±{forecast.addlocity_std:.2g} · "
            f"окно {forecast.sprint_length_days}д · отчёт {forecast.report_date.isoformat()}"
        ),
        fontsize=8,
        color="#555555",
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    return output
