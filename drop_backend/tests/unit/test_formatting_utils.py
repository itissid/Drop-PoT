import unittest
from datetime import datetime

from drop_backend.utils.formatting import (
    format_event_summary,
)  # Assuming format_event_summary is in 'your_module'
from drop_backend.utils.ors import TransitDirectionSummary, Units


class TestFormatEventSummary(unittest.TestCase):
    def setUp(self):
        self.current_datetime = datetime.strptime(
            "2023-09-01 15:00", "%Y-%m-%d %H:%M"
        )
        self.now_window_hours = 1
        self.when_now = "now"
        self.when_later = "later"

    def test_case_1(self):
        # CASE 1: Event is ongoing and when == now
        event_data = {
            "closest_walking_distance_and_duration": TransitDirectionSummary(
                1609.34,
                900,
                Units("meters", "seconds"),
            ),
            "start_date": "2023-09-01",
            "start_time": "14:00",
        }
        expected_output = "1.0 mi from you, happening @now"
        self.assertEqual(
            format_event_summary(
                event_data,
                self.when_now,
                self.now_window_hours,
                self.current_datetime,
            ),
            expected_output,
        )

    def test_case_2(self):
        # CASE 2: Event will begin within an hour and when == now
        event_data = {
            "closest_walking_distance_and_duration": TransitDirectionSummary(
                1609.34,
                900,
                Units("meters", "seconds"),
            ),
            "start_date": "2023-09-01",
            "start_time": "15:25",
        }
        expected_output = "1.0 mi from you, happening in 25 mins"
        self.assertEqual(
            format_event_summary(
                event_data,
                self.when_now,
                self.now_window_hours,
                self.current_datetime,
            ),
            expected_output,
        )

    def test_case_3(self):
        # CASE 3: Event starts on the same day but later and when == later
        event_data = {
            "closest_walking_distance_and_duration": None,
            "start_date": "2023-09-01",
            "start_time": "16:00",
        }
        expected_output = "happening at 4:00 PM"
        self.assertEqual(
            format_event_summary(
                event_data,
                self.when_later,
                self.now_window_hours,
                self.current_datetime,
            ),
            expected_output,
        )

    def test_case_4(self):
        # CASE 4: Event happens the next day and when == later
        event_data = {
            "closest_walking_distance_and_duration": TransitDirectionSummary(
                1609.34,
                900,
                Units("meters", "seconds"),
            ),
            "start_date": "2023-09-02",
            "start_time": "15:00",
        }
        expected_output = "1.0 mi from you, happening on 2nd Sep @ 3:00 PM"
        self.assertEqual(
            format_event_summary(
                event_data,
                self.when_later,
                self.now_window_hours,
                self.current_datetime,
            ),
            expected_output,
        )
