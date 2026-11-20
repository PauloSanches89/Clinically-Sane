"""Live queue estimates and saved clinic metrics.

Live pins use people who are still waiting. Averages use people who have
already been seen. A quiet day is not a closure.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from statistics import median


def _percent_away(value: float, center: float) -> float:
    base = abs(center) if abs(center) >= 1 else 1.0
    return abs(value - center) / base


def _values(reports: list[dict], key: str) -> list[float]:
    return [float(report[key]) for report in reports if report.get(key) is not None]


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(median(values))


def _is_outlier(report: dict, median_minutes: float | None, median_line: float | None) -> bool:
    if (
        report["minutes"] is None
        or report["line_length"] is None
        or median_minutes is None
        or median_line is None
    ):
        return False
    return (
        _percent_away(report["minutes"], median_minutes) > 0.5
        and _percent_away(report["line_length"], median_line) > 0.5
    )


def _spread(report: dict, median_minutes: float | None, median_line: float | None) -> float:
    total = 0.0
    compared = False
    if report["minutes"] is not None and median_minutes is not None:
        total += abs(report["minutes"] - median_minutes)
        compared = True
    if report["line_length"] is not None and median_line is not None:
        total += abs(report["line_length"] - median_line)
        compared = True
    return total if compared else float("inf")


def live_estimate(reports: list[dict], now: datetime) -> dict:
    """Still-waiting reports count until the end of their SAST calendar day."""
    today = now.date()
    recent = [
        report
        for report in reports
        if report["still_waiting"] and report["created_at"].date() == today
    ]
    if not recent:
        return {
            "stale": True,
            "confidence": "none",
            "minutes": None,
            "line_length": None,
            "report_count": 0,
            "consistent_id": None,
            "outlier_ids": [],
        }

    median_minutes = _median(_values(recent, "minutes"))
    median_line = _median(_values(recent, "line_length"))
    outlier_ids: list[int] = []
    used = recent
    if len(recent) >= 3 and median_minutes is not None and median_line is not None:
        outlier_ids = [
            report["id"]
            for report in recent
            if _is_outlier(report, median_minutes, median_line)
        ]
        kept = [report for report in recent if report["id"] not in outlier_ids]
        if kept:
            used = kept
            median_minutes = _median(_values(used, "minutes"))
            median_line = _median(_values(used, "line_length"))

    closest = min(used, key=lambda report: _spread(report, median_minutes, median_line))
    count = len(recent)
    if count == 1:
        confidence = "low"
    elif count == 2:
        confidence = "medium"
    else:
        confidence = "high"
    return {
        "stale": False,
        "confidence": confidence,
        "minutes": None if median_minutes is None else int(round(median_minutes)),
        "line_length": None if median_line is None else int(round(median_line)),
        "report_count": count,
        "consistent_id": closest["id"],
        "outlier_ids": outlier_ids,
    }


def average_wait(reports: list[dict], now: datetime) -> dict:
    seen = [
        report
        for report in reports
        if not report["still_waiting"] and report.get("minutes") is not None
    ]
    week_start = now - timedelta(days=7)
    recent = [report for report in seen if report["created_at"] >= week_start]

    def mean(rows: list[dict]) -> float | None:
        if not rows:
            return None
        return round(sum(row["minutes"] for row in rows) / len(rows), 1)

    return {
        "all_time": mean(seen),
        "all_time_count": len(seen),
        "last_7_days": mean(recent),
        "last_7_days_count": len(recent),
    }


def service_record(
    first_day: date | None,
    today: date,
    confirmed_closure_days: set[date],
) -> dict:
    if first_day is None or first_day > today:
        return {"issue_free_days": 0, "closure_days": 0}
    closure_days = sum(1 for day in confirmed_closure_days if first_day <= day <= today)
    span = (today - first_day).days + 1
    return {
        "issue_free_days": span - closure_days,
        "closure_days": closure_days,
    }
