"""Daily reports fold into running clinic averages.

A finished visit updates the stored sum and count. The average is sum / count,
which is the weighted mean of each day's average by that day's report count.
"""

from __future__ import annotations

from datetime import date, timedelta


def empty_today(day: str) -> dict:
    return {"day": day, "reports": [], "closures": [], "rates": {}}


def empty_stats() -> dict:
    return {"clinics": {}}


def empty_clinic() -> dict:
    return {
        "minutes_count": 0,
        "minutes_sum": 0,
        "line_count": 0,
        "line_sum": 0,
        "days": [],
        "closure_days": 0,
        "first_day": None,
    }


def _clinic(stats: dict, clinic_id: str) -> dict:
    clinics = stats.setdefault("clinics", {})
    slot = clinics.get(clinic_id)
    if slot is None:
        slot = empty_clinic()
        clinics[clinic_id] = slot
    return slot


def _totals(rows: list[dict], key: str) -> tuple[int, float]:
    values = [row[key] for row in rows if row.get(key) is not None]
    return len(values), float(sum(values))


def fold_day(stats: dict, today_doc: dict, new_day: date) -> dict:
    """Move one finished day into the running totals. Still-waiting reports stay out."""
    folded = {
        "clinics": {
            clinic_id: {
                **empty_clinic(),
                **slot,
                "days": [dict(bucket) for bucket in slot.get("days", [])],
            }
            for clinic_id, slot in stats.get("clinics", {}).items()
        }
    }
    day = today_doc.get("day")
    if not day or day >= new_day.isoformat():
        return folded

    seen: dict[str, list[dict]] = {}
    touched: set[str] = set()
    for report in today_doc.get("reports", []):
        touched.add(report["clinic_id"])
        if report.get("still_waiting"):
            continue
        seen.setdefault(report["clinic_id"], []).append(report)

    closures: dict[str, set[str]] = {}
    for flag in today_doc.get("closures", []):
        touched.add(flag["clinic_id"])
        closures.setdefault(flag["clinic_id"], set()).add(flag["reporter_hash"])

    cutoff = (new_day - timedelta(days=6)).isoformat()
    for clinic_id in touched:
        slot = _clinic(folded, clinic_id)
        rows = seen.get(clinic_id, [])
        minutes_count, minutes_sum = _totals(rows, "minutes")
        line_count, line_sum = _totals(rows, "line_length")
        slot["minutes_count"] += minutes_count
        slot["minutes_sum"] += minutes_sum
        slot["line_count"] += line_count
        slot["line_sum"] += line_sum
        slot["days"].append(
            {
                "day": day,
                "minutes_count": minutes_count,
                "minutes_sum": minutes_sum,
                "line_count": line_count,
                "line_sum": line_sum,
            }
        )
        slot["days"] = [bucket for bucket in slot["days"] if bucket["day"] >= cutoff]
        if len(closures.get(clinic_id, ())) >= 2:
            slot["closure_days"] += 1
        if slot["first_day"] is None:
            slot["first_day"] = day
    return folded


def _mean(total: float, count: int) -> float | None:
    if not count:
        return None
    return round(total / count, 1)


def displayed_averages(slot: dict | None, seen_rows: list[dict], today: date) -> dict:
    """Running totals plus finished visits already saved today."""
    base = slot or empty_clinic()
    today_minutes_count, today_minutes_sum = _totals(seen_rows, "minutes")
    today_line_count, today_line_sum = _totals(seen_rows, "line_length")
    cutoff = (today - timedelta(days=6)).isoformat()
    week_minutes_count = today_minutes_count
    week_minutes_sum = today_minutes_sum
    week_line_count = today_line_count
    week_line_sum = today_line_sum
    for bucket in base.get("days", []):
        if bucket["day"] < cutoff:
            continue
        week_minutes_count += bucket["minutes_count"]
        week_minutes_sum += bucket["minutes_sum"]
        week_line_count += bucket["line_count"]
        week_line_sum += bucket["line_sum"]
    return {
        "all_time": _mean(base["minutes_sum"] + today_minutes_sum, base["minutes_count"] + today_minutes_count),
        "all_time_count": base["minutes_count"] + today_minutes_count,
        "last_7_days": _mean(week_minutes_sum, week_minutes_count),
        "last_7_days_count": week_minutes_count,
        "line_all_time": _mean(base["line_sum"] + today_line_sum, base["line_count"] + today_line_count),
        "line_all_time_count": base["line_count"] + today_line_count,
        "line_last_7_days": _mean(week_line_sum, week_line_count),
        "line_last_7_days_count": week_line_count,
    }
