# Entry point for all commands. Set up things here like DB, logging or whatever.
import logging
from datetime import datetime
from typing import Any, Dict, List, cast

from ..model.persistence_model import (
    GeoAddresses,
    MoodSubmoodTable,
    ParsedEventTable,
    fetch_events_geocoded_mood_attached,
    should_include_event,
)
from ..utils.ors import get_transit_distance_duration
from ..webdemo.backend.app.custom_types import When

logger = logging.getLogger(__name__)


def geotag_moodtag_events_helper(
    engine,
    filename: str,
    version: str,
    where_lat: float,
    where_lon: float,
    datetime_now: datetime,
    when: When = When.NOW,
    now_window_hours: int = 1,
    fetched_data_cols=[
        ParsedEventTable.id,
        ParsedEventTable.event_json,
        ParsedEventTable.name,
        ParsedEventTable.description,
        GeoAddresses.latitude,
        GeoAddresses.longitude,
        MoodSubmoodTable.mood,
        MoodSubmoodTable.submood,
    ],
):
    """
    Identical to the above method but instead of typer.Context it takes a generic object which the
    session_manager decorator can extract the engine from.
    """
    context = object()
    context.obj = {}
    context.obj["engine"] = engine
    events: List[ParsedEventTable] = fetch_events_geocoded_mood_attached(
        context,
        filename,
        version,
        columns=fetched_data_cols,
    )

    # Calculate the time threshold
    filtered_events = []
    for event in events:
        if event.event_json and should_include_event(
            when,
            datetime_now,
            now_window_hours,
            cast(Dict[str, Any], event.event_json),
        ):
            assert event.latitude and event.longitude
            event_lat: float = event.latitude
            event_long: float = event.longitude
            # N2S: Could be lazy loaded by the web framework if found to be slow.
            directions = None
            try:
                directions = get_transit_distance_duration(
                    where_lat, where_lon, event_lat, event_long
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception(exc)

            filtered_events.append(
                {
                    "event": event,
                    "directions": directions,
                }
            )

    return filtered_events
