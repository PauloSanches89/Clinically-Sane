import unittest
from datetime import date, datetime, timedelta, timezone

from app.consensus import average_wait, live_estimate, service_record
from app.moderate import review_note

SAST = timezone(timedelta(hours=2))
NOW = datetime(2026, 11, 17, 14, 0, tzinfo=SAST)


def report(report_id, minutes, line, waiting=True, minutes_ago=10):
    return {
        "id": report_id,
        "minutes": minutes,
        "line_length": line,
        "still_waiting": waiting,
        "created_at": NOW - timedelta(minutes=minutes_ago),
    }


class ConsensusTests(unittest.TestCase):
    def test_single_report_is_low_confidence(self):
        live = live_estimate([report(1, 40, 12)], NOW)
        self.assertEqual(live["confidence"], "low")
        self.assertEqual(live["minutes"], 40)
        self.assertEqual(live["consistent_id"], 1)
        self.assertFalse(live["stale"])

    def test_seen_reports_do_not_invent_a_live_queue(self):
        live = live_estimate([report(1, 90, 20, waiting=False)], NOW)
        self.assertTrue(live["stale"])
        self.assertIsNone(live["minutes"])

    def test_earlier_today_stays_active(self):
        live = live_estimate([report(1, 30, 4, minutes_ago=300)], NOW)
        self.assertFalse(live["stale"])
        self.assertEqual(live["minutes"], 30)

    def test_yesterday_waiting_report_expires(self):
        live = live_estimate([report(1, 30, 4, minutes_ago=24 * 60)], NOW)
        self.assertTrue(live["stale"])

    def test_outlier_leaves_the_median(self):
        rows = [
            report(1, 30, 10),
            report(2, 32, 11),
            report(3, 28, 9),
            report(4, 200, 80),
        ]
        live = live_estimate(rows, NOW)
        self.assertIn(4, live["outlier_ids"])
        self.assertEqual(live["minutes"], 30)
        self.assertEqual(live["confidence"], "high")

    def test_average_ignores_people_still_waiting(self):
        rows = [
            report(1, 20, 5, waiting=False, minutes_ago=60),
            report(2, 40, 5, waiting=False, minutes_ago=30),
            report(3, 200, 5, waiting=True),
        ]
        stats = average_wait(rows, NOW)
        self.assertEqual(stats["all_time"], 30)
        self.assertEqual(stats["all_time_count"], 2)
        self.assertEqual(stats["last_7_days_count"], 2)

    def test_empty_average(self):
        stats = average_wait([report(1, 10, 2, waiting=True)], NOW)
        self.assertIsNone(stats["all_time"])
        self.assertEqual(stats["all_time_count"], 0)

    def test_uptime_needs_two_flags(self):
        record = service_record(date(2026, 11, 15), date(2026, 11, 17), {date(2026, 11, 16)})
        self.assertEqual(record, {"issue_free_days": 2, "closure_days": 1})

    def test_partial_report_fills_only_its_number(self):
        rows = [
            report(1, 30, 10),
            report(2, 40, None),
            report(3, None, 12),
        ]
        live = live_estimate(rows, NOW)
        self.assertEqual(live["minutes"], 35)
        self.assertEqual(live["line_length"], 11)
        self.assertEqual(live["report_count"], 3)
        self.assertEqual(live["outlier_ids"], [])

    def test_average_skips_a_seen_visit_without_minutes(self):
        rows = [
            report(1, 20, 5, waiting=False),
            report(2, None, 8, waiting=False),
        ]
        stats = average_wait(rows, NOW)
        self.assertEqual(stats["all_time"], 20.0)
        self.assertEqual(stats["all_time_count"], 1)

    def test_no_history_is_zero(self):
        self.assertEqual(
            service_record(None, date(2026, 11, 17), set()),
            {"issue_free_days": 0, "closure_days": 0},
        )

    def test_note_filter_keeps_a_queue_complaint(self):
        self.assertEqual(review_note("   "), (None, "none"))
        self.assertEqual(review_note("The wait is too long."), ("The wait is too long.", "kept"))
        self.assertEqual(
            review_note("Only one consulting room is open."),
            ("Only one consulting room is open.", "kept"),
        )
        self.assertEqual(
            review_note("Only two nurses are working today."),
            ("Only two nurses are working today.", "kept"),
        )
        self.assertEqual(
            review_note("Staff sent us away at the gate."),
            ("Staff sent us away at the gate.", "kept"),
        )
        self.assertEqual(review_note("This wait is killing me."), ("This wait is killing me.", "kept"))

    def test_note_filter_rejects_inappropriate_text(self):
        self.assertEqual(review_note("queue 0821234567 and 8001015009087 long")[1], "rejected")
        self.assertEqual(review_note("I will hurt Nurse Thandi.")[1], "rejected")
        self.assertEqual(review_note("Nurse Thandi was rude.")[1], "rejected")
        self.assertEqual(review_note("Dr van Wyk ignored the line.")[1], "rejected")
        self.assertIsNone(review_note("I will hurt Nurse Thandi.")[0])
        self.assertEqual(review_note("what a kaffir")[1], "rejected")


if __name__ == "__main__":
    unittest.main()
