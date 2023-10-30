import unittest
from datetime import datetime

from drop_backend.model.persistence_model import should_include_event
from drop_backend.webdemo.backend.app.custom_types import When


class TestShouldIncludeEvent(unittest.TestCase):
    def test_ongoing_event(self):
        """
        This test verifies that an ongoing event is included regardless of the
        current time. An event marked as "ongoing" should always be included in
        the results when querying for current events.
        """
        event_json = {"is_ongoing": True}
        self.assertTrue(
            should_include_event(When.NOW, datetime.now(), 6, event_json)
        )
        self.assertFalse(
            should_include_event(When.LATER, datetime.now(), 6, event_json)
        )

    def test_full_day_event(self):
        """Mainly if the event is already started its happening Now and not
        later. Exclude events outside these time ranges.
        """
        event_json = {
            "start_date": ["2023-07-15"],
            "end_date": ["2023-07-28"],
            "start_time": None,
            "end_time": None,
            "is_ongoing": True,
        }
        self.assertFalse(
            should_include_event(When.NOW, datetime.now(), 6, event_json)
        )
        self.assertTrue(
            should_include_event(
                When.NOW,
                datetime.strptime("2023-07-16 20:00", "%Y-%m-%d %H:%M"),
                6,
                event_json,
            )
        )
        self.assertFalse(
            should_include_event(
                When.NOW,
                datetime.strptime("2023-07-14 12:00", "%Y-%m-%d %H:%M"),
                6,
                event_json,
            )
        )

    def test_end_given_but_not_start_day_event(self):
        """
        Assume that the event is ongoing if no start.
        """
        event_json = {
            "start_date": None,
            "end_date": ["2023-07-28"],
            "start_time": None,
            "end_time": None,
            "is_ongoing": True,
        }
        self.assertTrue(
            should_include_event(
                When.NOW,
                datetime.strptime("2023-07-28 23:59", "%Y-%m-%d %H:%M"),
                6,
                event_json,
            )
        )
        # Assume all day.
        self.assertTrue(
            should_include_event(
                When.NOW,
                datetime.strptime("2023-07-27 00:00", "%Y-%m-%d %H:%M"),
                6,
                event_json,
            )
        )
        self.assertFalse(
            should_include_event(
                When.LATER,
                datetime.strptime("2023-07-27 20:00", "%Y-%m-%d %H:%M"),
                6,
                event_json,
            )
        )
        event_json = {
            "start_date": None,
            "end_date": ["2023-07-28"],
            "start_time": None,
            "end_time": ["21:00"],
            "is_ongoing": True,
        }
        self.assertFalse( # No start times but now > end time.
            should_include_event(
                When.NOW,
                datetime.strptime("2023-07-28 23:59", "%Y-%m-%d %H:%M"),
                6,
                event_json,
            )
        )
        self.assertTrue( # edge case
            should_include_event(
                When.NOW,
                datetime.strptime("2023-07-28 20:59", "%Y-%m-%d %H:%M"),
                6,
                event_json,
            )
        )
        self.assertTrue(  # The time now does not matter if the event is ongoing.
            should_include_event(
                When.NOW,
                datetime.strptime("2023-07-28 00:00", "%Y-%m-%d %H:%M"),
                6,
                event_json,
            )
        )
        self.assertFalse(  # The time now does not matter if the event is ongoing.
            should_include_event(
                When.LATER,
                datetime.strptime("2023-07-28 12:00", "%Y-%m-%d %H:%M"),
                6,
                event_json,
            )
        )

    def test_multiple_occurrences(self):
        event_json = {
            "start_date": ["2023-07-14", "2023-07-15"],
            "end_date": ["2023-07-14", "2023-07-15"],
            "start_time": ["19:30", "21:45", "18:30", "21:00"],
            "end_time": ["21:30", "23:45", "19:30", "22:00"],
        }
        self.assertTrue(
            should_include_event(
                When.NOW,
                datetime.strptime("2023-07-14 20:00", "%Y-%m-%d %H:%M"),
                6,
                event_json,
            )
        )

    def test_all_fields_null(self):
        event_json = {
            "start_date": None,
            "end_date": None,
            "start_time": None,
            "end_time": None,
            "is_ongoing": True,
        }
        self.assertTrue(
            should_include_event(When.NOW, datetime.now(), 6, event_json)
        )
        self.assertFalse(
            should_include_event(When.LATER, datetime.now(), 6, event_json)
        )

    def test_future_event(self):
        event_json = {
            "start_date": ["2023-07-16"],
            "end_date": ["2023-07-16"],
            "start_time": ["11:00"],
            "end_time": ["16:00"],
        }
        self.assertFalse(
            should_include_event(
                When.NOW,
                datetime.strptime("2023-07-14 20:00", "%Y-%m-%d %H:%M"),
                6,
                event_json,
            )
        )
        self.assertTrue(
            should_include_event(
                When.LATER,
                datetime.strptime("2023-07-14 20:00", "%Y-%m-%d %H:%M"),
                6,
                event_json,
            )
        )

    def test_missing_dates(self):
        """Will never return true"""
        event_json = {
            "start_date": None,
            "end_date": None,
            "start_time": ["11:00"],
            "end_time": ["16:00"],
        }
        self.assertFalse(
            should_include_event(When.NOW, datetime.now(), 6, event_json)
        )
        self.assertFalse(
            should_include_event(When.LATER, datetime.now(), 6, event_json)
        )

    def test_missing_end_dates_and_times(self):
        event_json = {
            "start_date": ["2023-07-16"],
            "start_time": ["11:00"],
            "end_date": None,
            "end_time": None,
        }
        self.assertTrue(
            should_include_event(
                When.NOW,
                datetime.strptime("2023-07-16 10:00", "%Y-%m-%d %H:%M"),
                6,
                event_json,
            )
        )
