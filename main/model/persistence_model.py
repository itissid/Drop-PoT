"""
Models used for abstracting away data operations.
"""
import logging
from dataclasses import asdict
from typing import Dict, List, Optional

from sqlalchemy import (
    JSON,
    Column,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from main.model.ai_conv_types import MessageNode
from main.model.types import Event

logger = logging.getLogger(__name__)

Base = declarative_base()


class ParsedEventTable(Base):
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
    parsed_event_embedding = relationship(
        "ParsedEventEmbeddingsTable",
        uselist=False,
        back_populates="parsed_event",
    )
    geo_addresses = relationship(
        "GeoAddresses", back_populates="related_parsed_events"
    )


class GeoAddresses(Base):
    __tablename__ = "GeoAddresses"
    id = Column(Integer, primary_key=True)
    parsed_event_id = Column(Integer, ForeignKey("parsed_events.id"))
    address = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    failure_reason = Column(String, nullable=True)
    related_parsed_events = relationship(
        "ParsedEventTable", back_populates="geo_addresses"
    )


def add_geoaddress(
    engine,
    parsed_event_id: int,
    address: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    failure_reason: Optional[str] = None,
):
    session = sessionmaker(bind=engine)()  # pylint ignore=invalid-name
    try:
        geo_address = GeoAddresses(
            parsed_event_id=parsed_event_id,
            address=address,
            latitude=latitude,
            longitude=longitude,
            failure_reason=failure_reason,
        )
        session.add(geo_address)
        session.commit()
    except SQLAlchemyError as error:
        session.rollback()
        logger.error("Failed to add geo address %s to database!", address)
        logger.exception(error)
    finally:
        session.close()


class ParsedEventEmbeddingsTable(Base):
    __tablename__ = "ParsedEventEmbeddingsTable"

    id = Column(Integer, primary_key=True)
    description_embedding = Column(LargeBinary, nullable=False)
    embedding_version = Column(String, nullable=False)

    parsed_event_id = Column(Integer, ForeignKey("parsed_events.id"))
    parsed_event = relationship(
        "ParsedEventTable", back_populates="parsed_event_embedding"
    )


def add_event(
    engine,
    event: Optional[Event],
    original_text: str,
    failure_reason: Optional[str],
    replay_history: Optional[List[MessageNode]],
    filename: str,
    version: str,
    chat_history: Optional[List[str]] = None,
) -> int:
    session = sessionmaker(bind=engine)()  # pylint: disable=invalid-name
    if event:
        event_dict = asdict(event)
        event_dict.pop("name", None)
        event_dict.pop("description", None)
    else:
        event_dict = None
    try:
        replay_history_json = None
        if replay_history:
            replay_history_json = [
                message.model_dump(mode="json") for message in replay_history
            ]
        event_table = ParsedEventTable(
            name=event.name if event else None,
            description=event.description if event else None,
            event_json=event_dict,
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

    finally:
        session.close()
    return -1


def get_max_id_by_version_and_filename(engine, version, filename):
    session = sessionmaker(bind=engine)()  # pylint ignore=invalid-name

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
    finally:
        session.close()


# Generated via Copilot
def get_num_events_by_version_and_filename(
    engine, version: str, filename: str
) -> int:
    session = sessionmaker(bind=engine)()  # pylint: disable=invalid-name

    try:
        # Query the database for the number of events with the given version and filename
        num_events = (
            session.query(func.count(ParsedEventTable.id))
            .filter(
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
    finally:
        session.close()
    return 0


def get_column_by_version_and_filename(
    engine, column: str, version: str, filename: str
) -> List[str]:
    session = sessionmaker(bind=engine)()  # pylint ignore=invalid-name
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
    finally:
        session.close()
    return []


def get_parsed_events(
    engine,
    filename: str,
    version: str,
    columns: Optional[List[Column]] = None,
) -> List[ParsedEventTable]:
    session = sessionmaker(bind=engine)()  # pylint ignore=invalid-name
    try:
        # Query the database for the given column with the given version and filename
        query = (
            session.query(ParsedEventTable)
            .filter(ParsedEventTable.version == version)
            .filter(ParsedEventTable.filename == filename)
        )
        if columns:
            query = query.with_entities(*columns)
        parsed_events = query.all()
        # add all parsed_events to a dictionary
        return parsed_events

    except SQLAlchemyError as exc:
        logger.exception(exc)
        raise exc
    finally:
        session.close()


# Note to self: What relationship do our document embeddings have with the Moods?
# How do I add relationships between them so it is easy to retrieve them later?
# How can I relate them to a person's input so that I can personalize what someone sees?


def insert_parsed_event_embeddings(engine, events: List[Dict[str, str]]):
    session = sessionmaker(bind=engine)()  # pylint ignore=invalid-name
    # Query the database for the given column with the given version and filename
    embedding_lst = []
    for parsed_event in events:
        parsed_event_embedding = ParsedEventEmbeddingsTable(
            description_embedding=parsed_event["embedding_vector"],
            embedding_version=parsed_event["version"],
            parsed_event_id=int(parsed_event["id"]),
        )
        embedding_lst.append(parsed_event_embedding)
    try:
        session.add_all(embedding_lst)
        session.commit()
    finally:
        session.close()
