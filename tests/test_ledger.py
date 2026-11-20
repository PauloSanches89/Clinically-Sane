from datetime import date

from app.ledger import displayed_averages, empty_stats, fold_day


def test_line_average_weights_each_day_by_its_report_count():
    today = {"day": "2026-11-19", "reports": [], "closures": []}
    for _ in range(5):
        today["reports"].append(
            {"clinic_id": "wyn", "still_waiting": False, "minutes": None, "line_length": 5}
        )
    stats = fold_day(empty_stats(), today, date(2026, 11, 20))
    next_day = {"day": "2026-11-20", "reports": [], "closures": []}
    for _ in range(2):
        next_day["reports"].append(
            {"clinic_id": "wyn", "still_waiting": False, "minutes": None, "line_length": 6}
        )
    stats = fold_day(stats, next_day, date(2026, 11, 21))
    shown = displayed_averages(stats["clinics"]["wyn"], [], date(2026, 11, 21))
    assert shown["line_all_time"] == 5.3
    assert shown["line_all_time_count"] == 7


def test_still_waiting_reports_stay_out_of_the_average():
    today = {
        "day": "2026-11-19",
        "reports": [
            {"clinic_id": "wyn", "still_waiting": True, "minutes": 40, "line_length": 9},
            {"clinic_id": "wyn", "still_waiting": False, "minutes": 10, "line_length": None},
        ],
        "closures": [],
    }
    stats = fold_day(empty_stats(), today, date(2026, 11, 20))
    slot = stats["clinics"]["wyn"]
    assert slot["minutes_count"] == 1
    assert slot["minutes_sum"] == 10
    assert slot["line_count"] == 0
