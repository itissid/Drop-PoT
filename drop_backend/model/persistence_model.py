"""
Models used for abstracting away data operations.
"""
import logging
from dataclasses import asdict
from typing import Dict, List, Optional

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
    func,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint

from ..utils.db_utils import session_manager
from .ai_conv_types import MessageNode

logger = logging.getLogger(__name__)

Base = declarative_base()


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
        "GeoAddresses", back_populates="related_parsed_events"
    )


class GeoAddresses(Base):  # type: ignore
    __tablename__ = "GeoAddresses"
    id = Column(Integer, primary_key=True)
    parsed_event_id = Column(Integer, ForeignKey("parsed_events.id"))
    address = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    failure_reason = Column(String, nullable=True)
    related_parsed_events = relationship(  # type: ignore
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
            event_json=event.model_dump_json() if event is not None else None,
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
) -> List[ParsedEventTable]:
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
    return [e for e in parsed_events]


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
        parsed_event_embedding = ParsedEventEmbeddingsTable(
            embedding=event["embedding"],
            embedding_type=event["embedding_type"],
            embedding_version=event["embedding_version"],
            parsed_event_id=int(event["parsed_event_id"]),
        )
        embedding_lst.append(parsed_event_embedding)
    session.add_all(embedding_lst)