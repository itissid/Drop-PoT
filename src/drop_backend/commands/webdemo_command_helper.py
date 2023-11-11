# Entry point for all commands. Set up things here like DB, logging or whatever.
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import typer
from sqlalchemy.engine import Engine

from ..model.persistence_model import (
    GeoAddresses,
    MoodSubmoodTable,
    ParsedEventTable,
    fetch_events_geocoded_mood_attached,
    should_include_event,
)
from ..types.city_event import CityEvent
from ..types.custom_types import When
from ..utils.ors import (
    GeoLocation,
    Profile,
    TransitDirectionError,
    TransitDirectionSummary,
    TransitDistanceDurationCalculator,
)

logger = logging.getLogger(__name__)


@dataclass
class _DedupedEvent:
    """Deduped by event's id"""

    id: str
    event_json: Dict[str, Any]
    name: str
    description: str
    mood: str
    submood: str
    geo_dict: Dict[str, GeoLocation]


@dataclass
class TaggedEvent:
    event: _DedupedEvent
    directions: Optional[
        List[
            Tuple[
                Dict[
                    Profile,
                    Union[TransitDirectionSummary, TransitDirectionError],
                ],
                str,
            ]
        ]
    ]

def geotag_moodtag_events_helper(
    engine_or_context: Union[Engine, "typer.Context"],
    ors_api_endpoint: str,
    file_version_constraints: Dict[str, List[str]],
    where_lat: float,
    where_lon: float,
    datetime_now: datetime,
    when: When = When.NOW,
    now_window_hours: int = 1,
    fetched_data_cols=(
        ParsedEventTable.id,
        ParsedEventTable.event_json,
        ParsedEventTable.name,
        ParsedEventTable.description,
        GeoAddresses.latitude,
        GeoAddresses.longitude,
        GeoAddresses.address,
        MoodSubmoodTable.mood,
        MoodSubmoodTable.submood,
    ),
) -> List[TaggedEvent]:
    """
    Identical to the above method but instead of typer.Context it takes a generic object which the
    session_manager decorator can extract the engine from.
    """

    if isinstance(engine_or_context, Engine):

        class DummyContext:
            def __init__(self):
                self.obj = {}

        dummy_context = DummyContext()
        dummy_context.obj["engine"] = engine_or_context
    else:
        if isinstance(engine_or_context, typer.Context):
            dummy_context: typer.Context = engine_or_context  # type: ignore
        else:
            raise ValueError(
                "Invalid type for engine_or_context must be Engine or Context"
            )

    events: List[ParsedEventTable] = fetch_events_geocoded_mood_attached(
        dummy_context,
        file_version_constraints,
        columns=list(fetched_data_cols),
    )
    logger.info("Got %d events from database", len(events))
    # Group by event and aggregate the addresses:
    events_dict: Dict[Union[str, int], Any] = defaultdict(
        lambda: dict(geo_dict=dict())
    )
    for row in events:
        geo_dict = events_dict[row.id]["geo_dict"]
        assert row.latitude and row.longitude and row.address  # type: ignore

        geo_dict[row.address] = GeoLocation(  # type: ignore
            **{"latitude": row.latitude, "longitude": row.longitude}  # type: ignore
        )

        # Store the other fields for each parsed event
        events_dict[row.id].update(
            {
                "id": row.id,
                "event_json": row.event_json,
                "name": row.name,
                "description": row.description,
                "mood": row.mood,  # type: ignore
                "submood": row.submood,  # type: ignore
            }
        )

    # Now convert the aggregated data into a list of dictionaries or other desired format
    event_lst = [
        _DedupedEvent(
            **{
                "id": key,
                # TODO(Fix me). I accidentally dumped the json string into instead of
                # just giving sqlalchemy the object. So it took '{"a": 1}' and stored it as
                # '"{\"a\": 1}"' in the db. So we need to do this hack to get the json back.
                #
                "event_json": value["event_json"],
                "name": value["name"],
                "description": value["description"],
                "mood": value["mood"],
                "submood": value["submood"],
                "geo_dict": value["geo_dict"],
            }
        )
        for key, value in events_dict.items()
    ]
    # Calculate the time threshold
    filtered_events = []
    dist_dur_calc = TransitDistanceDurationCalculator(ors_api_endpoint)
    for event in event_lst:
        if event.event_json is not None and should_include_event(
            when,
            datetime_now,
            now_window_hours,
            cast(Dict[str, Any], event.event_json),
        ):
            # N2S: Could be lazy loaded by the web framework if found to be slow.
            directions: Optional[
                list[
                    tuple[
                        Dict[
                            Profile,
                            Union[
                                TransitDirectionSummary, TransitDirectionError
                            ],
                        ],
                        str,
                    ]
                ]
            ] = None
            try:
                directions = (
                    dist_dur_calc.get_transit_distance_duration_wrapper(
                        where_lat, where_lon, event.geo_dict
                    )
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception(exc)
            filtered_events.append(
                TaggedEvent(
                    event,
                    directions,
                )
            )

    return filtered_events
