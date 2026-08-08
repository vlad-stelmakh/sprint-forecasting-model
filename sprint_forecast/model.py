"""Core sprint forecasting calculations (Excel Formulas sheet logic)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import sqrt
from typing import Optional, Sequence

import numpy as np
from scipy.stats import norm


def _as_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


@dataclass(frozen=True)
class WorkItem:
    """One backlog item (Excel Plan row / future Jira issue)."""

    name: str
    estimate: float
    created: date | datetime
    completed: date | datetime | None = None

    @property
    def created_date(self) -> date:
        result = _as_date(self.created)
        assert result is not None
        return result

    @property
    def completed_date(self) -> date | None:
        return _as_date(self.completed)


@dataclass
class SprintRow:
    sprint_number: int
    start: date | None
    end: date | None
    done: float
    total_done: float | None
    trend_remaining: float | None
    added: float
    total_added: float
    upper: float | None  # "Вверх"
    lower: float | None  # "Низ"
    remaining: float | None
    trend_added: float | None
    prob_this_iteration: float | None
    n: int
    prob_finish_by: float | None


@dataclass
class SprintForecast:
    initial_backlog_size: float
    backlog_size: float
    sprint_length_days: int
    report_date: date
    current_sprint: int
    remaining_work: float
    velocity_mean: float
    velocity_std: float
    addlocity_mean: float
    addlocity_std: float
    sprints: list[SprintRow]


def _sample_stdev(values: Sequence[float]) -> float:
    """Excel STDEV (sample, n-1)."""
    arr = np.asarray(values, dtype=float)
    if arr.size < 2:
        return 0.0
    return float(arr.std(ddof=1))


def _linear_trend(
    known_y: Sequence[float],
    known_x: Sequence[float],
    new_x: Sequence[float],
) -> list[float]:
    """Excel TREND: least-squares line through known points, evaluate at new_x."""
    x = np.asarray(known_x, dtype=float)
    y = np.asarray(known_y, dtype=float)
    if x.size == 0:
        return [float("nan")] * len(new_x)
    if x.size == 1:
        return [float(y[0])] * len(new_x)
    slope, intercept = np.polyfit(x, y, 1)
    return [float(intercept + slope * xi) for xi in new_x]


def _sum_done_in_window(items: Sequence[WorkItem], start: date, end: date) -> float:
    total = 0.0
    for item in items:
        completed = item.completed_date
        if completed is not None and start <= completed < end:
            total += item.estimate
    return total


def _sum_added_in_window(items: Sequence[WorkItem], start: date, end: date) -> float:
    total = 0.0
    for item in items:
        if start <= item.created_date < end:
            total += item.estimate
    return total


def compute_forecast(
    items: Sequence[WorkItem],
    *,
    first_sprint_start: date,
    sprint_length_days: int = 7,
    sprint_count: int = 15,
    report_date: date | None = None,
) -> SprintForecast:
    """
    Replicate the Formulas sheet from sprint_planning.xlsx.

    Parameters mirror the spreadsheet:
    - first_sprint_start: Formulas!B13
    - sprint_length_days: Formulas!B3 (SprintLen)
    - sprint_count: number of sprints from 1..N (sheet uses 15)
    - report_date: Formulas!B4; defaults to max completion date
    """
    if not items:
        raise ValueError("items must not be empty")

    backlog_size = float(sum(item.estimate for item in items))
    initial_backlog_size = float(
        sum(item.estimate for item in items if item.created_date < first_sprint_start)
    )

    completed_dates = [item.completed_date for item in items if item.completed_date]
    if report_date is None:
        if not completed_dates:
            raise ValueError("report_date is required when no items are completed")
        report_date = max(completed_dates)

    # Sprint calendar: row 0 is the synthetic "Старт" row (A12), then 1..sprint_count
    starts: list[date | None] = [None]
    ends: list[date | None] = [None]
    for i in range(sprint_count):
        start = first_sprint_start + timedelta(days=sprint_length_days * i)
        end = start + timedelta(days=sprint_length_days)
        starts.append(start)
        ends.append(end)

    # Current sprint: INDEX/MATCH(report_date, starts, 1) — largest start <= report_date
    current_sprint = 0
    for num, start in enumerate(starts):
        if start is not None and start <= report_date:
            current_sprint = num
        elif start is None and num == 0:
            # B12 is numeric 0 in Excel; MATCH still can land on later dates
            continue

    done = [0.0]
    added = [0.0]
    for num in range(1, sprint_count + 1):
        start = starts[num]
        end = ends[num]
        assert start is not None and end is not None
        done.append(_sum_done_in_window(items, start, end))
        added.append(_sum_added_in_window(items, start, end))

    total_done: list[float | None] = [0.0]
    total_added = [0.0]
    cumulative_done = 0.0
    cumulative_added = 0.0
    for num in range(1, sprint_count + 1):
        cumulative_done += done[num]
        cumulative_added += added[num]
        total_added.append(cumulative_added)
        start = starts[num]
        assert start is not None
        if start > report_date:
            total_done.append(None)
        else:
            total_done.append(cumulative_done)

    upper: list[float | None] = [initial_backlog_size]
    lower: list[float | None] = [0.0]  # -H12, H12=0
    remaining: list[float | None] = [0.0]
    for num in range(1, sprint_count + 1):
        end = ends[num]
        assert end is not None
        if end > report_date:
            upper.append(None)
            lower.append(None)
            remaining.append(None)
        else:
            td = total_done[num]
            assert td is not None
            upper.append(max(0.0, initial_backlog_size - td))
            lower.append(-total_added[num])
            remaining.append(backlog_size - td)

    # Velocity / addlocity windows match Excel ranges:
    # AVERAGE(D13:D17) / STDEV(D13:D17) → sprints 1..5
    # AVERAGE(G12:G16) → sprints 0..4; STDEV(G12:G27) → sprints 0..15
    velocity_window = done[1:6]
    addlocity_mean_window = added[0:5]
    addlocity_std_window = added[0 : sprint_count + 1]

    velocity_mean = float(np.mean(velocity_window))
    velocity_std = _sample_stdev(velocity_window)
    addlocity_mean = float(np.mean(addlocity_mean_window))
    addlocity_std = _sample_stdev(addlocity_std_window)

    remaining_work = initial_backlog_size + sum(added) - sum(done)

    # TREND: known points are non-NA K13:K27 / J13:J27 with x = Excel row numbers 13..
    # Array formula spills from F12/L12 with new_x = rows 13..27
    excel_row_for_sprint = {num: 12 + num for num in range(sprint_count + 1)}
    known_remaining_x: list[float] = []
    known_remaining_y: list[float] = []
    known_lower_x: list[float] = []
    known_lower_y: list[float] = []
    for num in range(1, sprint_count + 1):
        row = excel_row_for_sprint[num]
        if remaining[num] is not None:
            known_remaining_x.append(float(row))
            known_remaining_y.append(float(remaining[num]))
        if lower[num] is not None:
            known_lower_x.append(float(row))
            known_lower_y.append(float(lower[num]))

    new_x = [float(excel_row_for_sprint[num]) for num in range(1, sprint_count + 1)]
    trend_remaining_vals = _linear_trend(known_remaining_y, known_remaining_x, new_x)
    trend_added_vals = _linear_trend(known_lower_y, known_lower_x, new_x)
    # Place predictions for rows 13..27 into F12..F26 / L12..L26 (shift by -1 index)
    trend_remaining: list[float | None] = [None] * (sprint_count + 1)
    trend_added: list[float | None] = [None] * (sprint_count + 1)
    for i, value in enumerate(trend_remaining_vals):
        # i=0 → prediction for row 13 → stored at sprint 0 (row 12)
        target = i  # sprint index
        if target <= sprint_count:
            trend_remaining[target] = value
    for i, value in enumerate(trend_added_vals):
        target = i
        if target <= sprint_count:
            trend_added[target] = value
    # Excel F27/L27 are outside the spill (or #N/A); leave last unused slot None if needed
    if sprint_count >= 15:
        # Sheet has F27 = #N/A explicitly; predictions fill F12:F26 only (15 values)
        pass

    # Probabilities
    n_values = [num - current_sprint for num in range(sprint_count + 1)]
    prob_finish: list[float | None] = []
    for n in n_values:
        if n > 0:
            mean = n * (velocity_mean - addlocity_mean)
            std = sqrt(n * (addlocity_std**2 + velocity_std**2))
            # 1 - NORM.DIST(remaining_work, mean, std, TRUE)
            if std == 0:
                prob = 1.0 if remaining_work < mean else 0.0
            else:
                prob = float(1.0 - norm.cdf(remaining_work, loc=mean, scale=std))
            prob_finish.append(prob)
        else:
            prob_finish.append(None)

    prob_iteration: list[float | None] = [None]
    for num in range(1, sprint_count + 1):
        prev = prob_finish[num - 1]
        cur = prob_finish[num]
        if prev is not None and cur is not None:
            prob_iteration.append(cur - prev)
        else:
            prob_iteration.append(None)

    sprints: list[SprintRow] = []
    for num in range(sprint_count + 1):
        sprints.append(
            SprintRow(
                sprint_number=num,
                start=starts[num],
                end=ends[num],
                done=done[num],
                total_done=total_done[num],
                trend_remaining=trend_remaining[num],
                added=added[num],
                total_added=total_added[num],
                upper=upper[num],
                lower=lower[num],
                remaining=remaining[num],
                trend_added=trend_added[num],
                prob_this_iteration=prob_iteration[num],
                n=n_values[num],
                prob_finish_by=prob_finish[num],
            )
        )

    return SprintForecast(
        initial_backlog_size=initial_backlog_size,
        backlog_size=backlog_size,
        sprint_length_days=sprint_length_days,
        report_date=report_date,
        current_sprint=current_sprint,
        remaining_work=remaining_work,
        velocity_mean=velocity_mean,
        velocity_std=velocity_std,
        addlocity_mean=addlocity_mean,
        addlocity_std=addlocity_std,
        sprints=sprints,
    )


def forecast_to_dataframe(forecast: SprintForecast):
    """Optional pandas view of per-sprint rows."""
    import pandas as pd

    rows = []
    for s in forecast.sprints:
        rows.append(
            {
                "sprint": s.sprint_number,
                "start": s.start,
                "end": s.end,
                "done": s.done,
                "total_done": s.total_done,
                "trend_remaining": s.trend_remaining,
                "added": s.added,
                "total_added": s.total_added,
                "upper": s.upper,
                "lower": s.lower,
                "remaining": s.remaining,
                "trend_added": s.trend_added,
                "prob_this_iteration": s.prob_this_iteration,
                "n": s.n,
                "prob_finish_by": s.prob_finish_by,
            }
        )
    return pd.DataFrame(rows)
