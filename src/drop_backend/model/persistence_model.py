"""
Models used for abstracting away data operations.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from sqlalchemy import (
    JSON,
    Column,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    and_,
    func,
    or_,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint

from ..types.custom_types import When
from ..utils.db_utils import session_manager
from .ai_conv_types import MessageNode
from .merge_base import Base
from .mood_model_supervised import MoodSubmoodTable, SubMoodEventTable

logger = logging.getLogger(__name__)

# Base = declarative_base()


class ParsedEventTable(Base):  # type: ignore
    """
    Table that holds the top level event and parsing info parsed from unstructured event data.
    """

    __tablename__ = "parsed_events"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=True)
    description = Column(String, nullable=True)
    event_json = Column(JSON, nullable=True)
    original_event = Column(Text, nullable=False)
    failure_reason = Column(String, nullable=True)
    filename = Column(String, nullable=False)
    chat_history = Column(JSON, nullable=True)
    replay_history = Column(JSON, nullable=True)
    version = Column(String, nullable=False)
    parsed_event_embedding = relationship(  # type: ignore
        "ParsedEventEmbeddingsTable",
        uselist=False,
        back_populates="parsed_event",
    )
    geo_addresses = relationship(  # type: ignore
        "GeoAddresses", back_populates="parsed_events"
    )
    sub_mood_event = relationship(
        "SubMoodEventTable", back_populates="parsed_events", uselist=False
    )


class GeoAddresses(Base):  # type: ignore
    __tablename__ = "GeoAddresses"
    id = Column(Integer, primary_key=True)
    parsed_event_id = Column(Integer, ForeignKey("parsed_events.id"))
    address = Column(String, nullable=False)
    # N2S: In hindsight it might not be a bad idea to use a fixed precision number
    # for latitude and longitude using something like: DECIMAL(10,5)
    # Maybe then I could have cached them easily as well.
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    failure_reason = Column(String, nullable=True)
    parsed_events = relationship(  # type: ignore
        "ParsedEventTable", back_populates="geo_addresses"
    )


@session_manager
def add_geoaddress(
    session,
    parsed_event_id: int,
    address: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    failure_reason: Optional[str] = None,
):
    try:
        geo_address = GeoAddresses(
            parsed_event_id=parsed_event_id,
            address=address,
            latitude=latitude,  # type: ignore
            longitude=longitude,  # type: ignore
            failure_reason=failure_reason,
        )
        session.add(geo_address)
        session.commit()
    except SQLAlchemyError as error:
        session.rollback()
        logger.error("Failed to add geo address %s to database!", address)
        logger.exception(error)
        raise error
    finally:
        session.close()


class ParsedEventEmbeddingsTable(Base):  # type: ignore
    __tablename__ = "ParsedEventEmbeddingsTable"

    id = Column(Integer, primary_key=True)
    embedding = Column(LargeBinary, nullable=False)
    embedding_version = Column(String, nullable=False)
    embedding_type = Column(
        Enum("description", "name", "name_description"),
        nullable=True,
    )

    parsed_event_id = Column(Integer, ForeignKey("parsed_events.id"))
    parsed_event = relationship(  # type: ignore
        "ParsedEventTable", back_populates="parsed_event_embedding"
    )
    __table_args__ = (
        UniqueConstraint(
            "parsed_event_id",
            "embedding_version",
            "embedding_type",
            name="uq_embedding_details",
        ),
    )


@session_manager
def add_event(
    session,
    event: Optional[BaseModel],
    original_text: str,
    failure_reason: Optional[str],
    replay_history: Optional[List[MessageNode]],
    filename: str,
    version: str,
    chat_history: Optional[List[str]] = None,
) -> int:
    try:
        replay_history_json = None
        if replay_history:
            replay_history_json = [
                message.model_dump(mode="json") for message in replay_history
            ]
        event_table = ParsedEventTable(
            name=event.name if event and "name" in event.model_fields else None,  # type: ignore
            description=event.description  # type: ignore
            if event and "description" in event.model_fields
            else None,
            event_json=event.model_dump(exclude=["name", "description"])
            if event is not None
            else None,
            original_event=original_text,
            replay_history=replay_history_json,
            chat_history=chat_history,
            failure_reason=failure_reason,
            filename=filename,
            version=version,
        )

        session.add(event_table)
        session.commit()
        return event_table.id  # type: ignore
    except SQLAlchemyError as error:
        session.rollback()
        logger.error("Failed to add event %s to database!", original_text)
        logger.exception(error)
        raise error


@session_manager
def get_max_id_by_version_and_filename(session, version, filename):
    try:
        # Query the database for the maximum id value with the given version and filename
        max_id = (
            session.query(
                func.max(ParsedEventTable.id)  # pylint: disable=not-callable
            )
            .filter(
                ParsedEventTable.version == version,
                ParsedEventTable.filename == filename,
            )
            .scalar()
        )
        return max_id
    except SQLAlchemyError as error:
        logger.error(
            "Failed to retrieve the max id from ParsedEventTable for version: %s and filename: %s!",
            version,
            filename,
        )
        logger.exception(error)
        raise error


# Generated via Copilot
@session_manager
def get_num_events_by_version_and_filename(
    session, version: str, filename: str
) -> int:
    try:
        # Query the database for the number of events with the given version and filename
        num_events = (
            session.query(
                func.count(ParsedEventTable.id)  # pylint: disable=not-callable
            )
            .filter(  # pylint: disable=not-callable
                ParsedEventTable.version == version,
                ParsedEventTable.filename == filename,
            )
            .scalar()
        )
        return num_events
    except SQLAlchemyError as error:
        logger.error(
            "Failed to retrieve the number of events from ParsedEventTable for version: %s  and filename: %s!",
            version,
            filename,
        )
        logger.exception(error)
        raise error


@session_manager
def get_column_by_version_and_filename(
    session, column: str, version: str, filename: str
) -> List[str]:
    try:
        # Query the database for the given column with the given version and filename
        column_values = (
            session.query(getattr(ParsedEventTable, column))
            .filter(
                ParsedEventTable.version == version,
                ParsedEventTable.filename == filename,
            )
            .all()
        )

        # The query returns a tuple, so we get the first item
        return [value[0] for value in column_values]
    except SQLAlchemyError as error:
        logger.error(
            "Failed to retrieve the %s from ParsedEventTable for version: %s and filename: %s!",
            column,
            version,
            filename,
        )
        logger.exception(error)
        raise error


@session_manager
def get_parsed_events(
    session,
    filename: str,
    version: str,
    columns: Optional[List[Column]] = None,
    parse_failed_only: bool = False,
) -> List[ParsedEventTable]:
    # Query the database for the given column with the given version and filename
    query = (
        session.query(ParsedEventTable)
        .filter(ParsedEventTable.version == version)
        .filter(ParsedEventTable.filename == filename)
    )
    if parse_failed_only:
        query = query.filter(
            or_(
                ParsedEventTable.failure_reason.isnot(None),
                ParsedEventTable.event_json.isnot(""),
            )
        )
    if columns:
        query = query.with_entities(*columns)
    parsed_events = query.all()
    # add all parsed_events to a dictionary
    return [e for e in parsed_events]


class GeoTaggedMoodTaggedEvents:
    id: int
    name: str
    description: str
    event_json: Dict[str, Any]
    latitude: float
    longitude: float
    mood: str
    submood: str


@session_manager
def fetch_events_geocoded_mood_attached(
    session,
    file_versions_constraints: Dict[str, List[str]],
    columns: Optional[List[Column]] = None,
) -> List[ParsedEventTable]:
    """
    Fetches events from the database based on filename and version,
    and obtains the latitude and longitude of each event from the GeoAddresses table.

    Parameters:
    - db (Session): The database session.
    - filename (str): The filename to filter events on.
    - version (str): The version to filter events on.
    - lat (float): Latitude of the reference location.
    - long (float): Longitude of the reference location.

    Returns:
    - List[models.ParsedEventTable]: A list of events.
    """
    # Build the base query
    query = (
        session.query(ParsedEventTable, GeoAddresses, MoodSubmoodTable)
        .join(GeoAddresses, ParsedEventTable.id == GeoAddresses.parsed_event_id)
        .join(
            SubMoodEventTable, ParsedEventTable.id == SubMoodEventTable.event_id
        )
        .join(
            MoodSubmoodTable,
            SubMoodEventTable.mood_sub_mood_id == MoodSubmoodTable.id,
        )
        .filter(
            or_(
                *[
                    and_(
                        ParsedEventTable.filename == filename,
                        ParsedEventTable.version.in_(versions),
                    )
                    for filename, versions in file_versions_constraints.items()
                ]
            )
        )
        .filter(GeoAddresses.latitude.isnot(None))
        .filter(GeoAddresses.longitude.isnot(None))
    )
    if columns:
        query = query.with_entities(*columns)

    # Fetch and return the events
    events = query.all()
    return [e for e in events]  # pylint: disable=unnecessary-comprehension


def compute_hours_diff(
    start_date_str: str,
    end_date_str: str,
    start_time_str: str,
    end_time_str: str,
    datetime_now: datetime,
):
    # Default to full day if time is not provided
    start_time_str = start_time_str or "00:00"
    end_time_str = end_time_str or "23:59"

    # Combine date and time strings into datetime objects
    start_datetime_str = f"{start_date_str} {start_time_str}"
    end_datetime_str = f"{end_date_str} {end_time_str}"

    # Convert to datetime objects
    # start_datetime = datetime.strptime(start_datetime_str, "%Y-%m-%d %H:%M")
    try:
        start_datetime = datetime.strptime(start_datetime_str, "%Y-%m-%d %H:%M")
    except ValueError:
        start_datetime = datetime.strptime(
            start_datetime_str, "%Y-%m-%d %H:%M:%S"
        )
    try:
        end_datetime = datetime.strptime(end_datetime_str, "%Y-%m-%d %H:%M")
    except ValueError:
        end_datetime = datetime.strptime(end_datetime_str, "%Y-%m-%d %H:%M:%S")

    # Compute hours difference from datetime_now
    hours_from_now_start = (
        start_datetime - datetime_now
    ).total_seconds() / 3600
    hours_from_now_end = (end_datetime - datetime_now).total_seconds() / 3600
    has_already_started = start_datetime <= datetime_now
    has_already_ended = end_datetime < datetime_now

    return (
        hours_from_now_start,
        hours_from_now_end,
        has_already_started,
        has_already_ended,
    )


def should_include_event(
    when: When,
    datetime_now: datetime,
    now_window: int,
    event_json: Dict[str, Any],
) -> bool:
    # TODO: accomodate for repetitive events.
    # Check if the event is marked as ongoing

    # Get date and time fields from event_json
    start_dates = event_json.get("start_date", []) or []
    end_dates = event_json.get("end_date", []) or []
    start_times = event_json.get("start_time", []) or []
    end_times = event_json.get("end_time", []) or []

    if (start_times and not start_dates) or (end_times and not end_dates):
        # IN valid data?
        # pylint: disable=logging-not-lazy
        msg = (
            f"Invalid data in event_json. Start times and End Times: {start_times}, {end_times}"
            + f" But end dates and start dates are empty for event: {event_json}"
        )
        logger.warning(msg)
        return False

    # If all date and time fields are null, skip this event
    if not any([start_dates, end_dates, start_times, end_times]):
        if event_json.get("is_ongoing", False):
            if when == When.NOW:
                return True

        return False

    max_occurrences = max(
        [len(start_dates), len(end_dates), len(start_times), len(end_times)]
    )
    for i in range(max_occurrences):
        start_date_str = (
            start_dates[i]
            if i < len(start_dates)
            else datetime_now.date().strftime(
                "%Y-%m-%d"
            )  # Assume the event starts now if its not mentioned
        )
        end_date_str = (
            end_dates[i] if i < len(end_dates) else start_date_str
        )  # default to start_date if end_date is not provided

        start_time_str = (
            start_times[i]
            if i < len(start_times)
            else (  # if the event does have a start_date then assume its a full day event starting at 00:00
                "00:00"
                if len(start_dates) < i
                else datetime_now.time().strftime(
                    "%H:%M"
                )  # else assume that since there is no event_start it starts at datetime_now, same as start_date
            )
        )
        end_time_str = end_times[i] if i < len(end_times) else "23:59"

        (
            hours_from_now_start,
            hours_from_now_end,
            has_already_started,
            has_already_ended,
        ) = compute_hours_diff(
            start_date_str,
            end_date_str,
            start_time_str,
            end_time_str,
            datetime_now,
        )

        if has_already_started and not has_already_ended:
            if when == When.NOW:
                return True
            return False

        if has_already_ended:
            return False

        if when == When.NOW:
            condition_now = (hours_from_now_start <= now_window) or (
                hours_from_now_end >= 0 and hours_from_now_end <= now_window
            )
            if condition_now:
                return True
        else:  # when == When.LATER
            condition_later = hours_from_now_start > now_window
            if condition_later:
                return True

    return False


@session_manager
def get_parsed_embeddings_by_version_and_filename(
    session, version: str, filename: str, embedding_type: str
):
    try:
        results = (
            session.query(
                ParsedEventTable.id,
                ParsedEventEmbeddingsTable.embedding,
                ParsedEventTable.description,
                ParsedEventTable.name,
                ParsedEventTable.event_json,
            )
            .join(
                ParsedEventEmbeddingsTable,
                ParsedEventTable.id
                == ParsedEventEmbeddingsTable.parsed_event_id,
            )
            .filter(
                ParsedEventTable.version == version,
                ParsedEventTable.filename == filename,
                ParsedEventEmbeddingsTable.embedding_type == embedding_type,
            )
            .all()
        )
        return results
    except SQLAlchemyError as error:
        logger.error(
            "Failed to retrieve data for version: %s and filename: %s!",
            version,
            filename,
        )
        logger.exception(error)
        raise error


@session_manager
def insert_parsed_event_embeddings(session, events: List[Dict[str, str]]):
    # Query the database for the given column with the given version and filename
    embedding_lst = []
    for event in events:
        parsed_event_embedding = ParsedEventEmbeddingsTable(  # type: ignore
            embedding=event["embedding"],
            embedding_type=event["embedding_type"],
            embedding_version=event["embedding_version"],
            parsed_event_id=int(event["parsed_event_id"]),
        )
        embedding_lst.append(parsed_event_embedding)
    session.add_all(embedding_lst)
