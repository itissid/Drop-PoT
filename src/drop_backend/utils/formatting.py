from datetime import datetime, timedelta
from typing import Optional, Union

from .datetime_utils import datetime_string_processor
from .ors import TransitDirectionSummary


def format_event_summary(
    event_data: dict,
    when: str,
    now_window_hours: int,
    current_datetime: datetime,
) -> Optional[str]:
    """
    For the closest address we generate a summary.
    """
    # Concatenate start_date and start_time to form the event's start datetime string
    start_datetime_str = event_data["start_time"]
    # Standartize the time stamp to %H:%M
    start_datetime_str_std = datetime_string_processor(
        start_datetime_str, ["%H:%M", "%H:%M:%S"], "%H:%M"
    )
    event_start_datetime_str = (
        f"{event_data['start_date']} {start_datetime_str_std}"
    )
    event_start_datetime_str = (
        f"{event_data['start_date']} {event_data['start_time']}"
    )

    event_start_datetime = datetime.strptime(
        event_start_datetime_str, "%Y-%m-%d %H:%M"
    )

    # Convert distance from meters to miles
    walking_distance_and_duration: Union[
        TransitDirectionSummary, None
    ] = event_data.get("closest_walking_distance_and_duration", None)
    distance_miles = None
    if walking_distance_and_duration:
        distance_miles = (
            walking_distance_and_duration.distance * 0.000621371
        )  # Convert meters to miles

    # Determine if the event is ongoing based on the start datetime
    is_ongoing = (event_start_datetime <= current_datetime) or (
        not event_data["start_date"] and not start_datetime_str_std
    )

    # Case 1: Event is ongoing and when == now
    if is_ongoing and when == "now":
        return (
            f"{distance_miles:.1f} mi from you, happening @now"
            if distance_miles is not None
            else "happening @now"
        )

    # Calculate the time difference between the current time and the event start time
    time_difference = event_start_datetime - current_datetime

    # Case 2: Event will begin within an hour and when == now
    if time_difference <= timedelta(hours=now_window_hours) and when == "now":
        minutes_until_start = time_difference.seconds // 60
        return (
            f"{distance_miles:.1f} mi from you, happening in {minutes_until_start} mins"
            if distance_miles is not None
            else f"happening in {minutes_until_start} mins"
        )

    # Case 3: Event starts on the same day and when == later
    if (
        event_start_datetime.date() == current_datetime.date()
        and when == "later"
    ):
        event_start_time_str = event_start_datetime.strftime("%l:%M %p")
        return (
            f"{distance_miles:.1f} mi from you, happening at {event_start_time_str}"
            if distance_miles is not None
            else f"happening at {event_start_time_str.strip()}"
        )

    # Case 4: Event happens the next day
    if event_start_datetime.date() > current_datetime.date():
        day_str = ordinal(event_start_datetime.day)
        event_date_time_str = event_start_datetime.strftime(
            f"{day_str} %b @%l:%M %p"
        )
        return (
            f"{distance_miles:.1f} mi from you, happening on {event_date_time_str}"
            if distance_miles is not None
            else f"happening on {event_date_time_str}"
        )

    # Default case: return a generic summary
    return None


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
