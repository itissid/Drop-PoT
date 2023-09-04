import json
import logging
from dataclasses import asdict
from typing import Dict, List, Optional

from dataclasses_json import DataClassJsonMixin, dataclass_json
from sqlalchemy import (JSON, Column, Engine, ForeignKey, Integer, LargeBinary,
                        String, Text, func, text)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from main.model.types import Event

logger = logging.getLogger(__name__)

Base = declarative_base()


class ParsedEventTable(Base):  # type: ignore
    __tablename__ = "parsed_events"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=True)
    description = Column(String, nullable=True)
    event_json = Column(JSON, nullable=True)
    original_event = Column(Text, nullable=False)
    failure_reason = Column(String, nullable=True)
    filename = Column(String, nullable=False)
    version = Column(String, nullable=False)
    parsed_event_embedding = relationship(
        "ParsedEventEmbeddingsTable", uselist=False, back_populates="parsed_event")


class ParsedEventEmbeddingsTable(Base):  # type: ignore
    __tablename__ = "ParsedEventEmbeddingsTable"

    id = Column(Integer, primary_key=True)
    description_embedding = Column(LargeBinary, nullable=False)
    embedding_version = Column(String, nullable=False)

    parsed_event_id = Column(Integer, ForeignKey("parsed_events.id"))
    parsed_event = relationship("ParsedEventTable", back_populates="parsed_event_embedding")


def add_event(
    engine: Engine,
    event: Optional[Event],
    original_text: str,
    failure_reason: Optional[str],
    filename: str,
    version: str,
) -> int:
    Session = sessionmaker(bind=engine)
    session = Session()
    if event:
        event_dict = asdict(event)
        event_dict.pop("name", None)
        event_dict.pop("description", None)
    else:
        event_dict = None
    try:
        event_table = ParsedEventTable(
            name=event.name if event else None,
            description=event.description if event else None,
            event_json=event_dict,
            original_event=original_text,
            failure_reason=failure_reason,
            filename=filename,
            version=version,
        )

        session.add(event_table)
        session.commit()
        return event_table.id  # type: ignore
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Failed to add event {original_text} to database!")
        logger.exception(e)

    finally:
        session.close()
    return -1


def get_max_id_by_version_and_filename(engine, version, filename):
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Query the database for the maximum id value with the given version and filename
        max_id = (
            session.query(func.max(ParsedEventTable.id))
            .filter(
                ParsedEventTable.version == version,
                ParsedEventTable.filename == filename,
            )
            .scalar()
        )
        return max_id
    except SQLAlchemyError as e:
        logger.error(
            f"Failed to retrieve the max id from ParsedEventTable for version: {version} and filename: {filename}!"
        )
        logger.exception(e)
    finally:
        session.close()


# Generated via Copilot
def get_num_events_by_version_and_filename(
    engine, version: str, filename: str
) -> int:
    Session = sessionmaker(bind=engine)
    session = Session()

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
    except SQLAlchemyError as e:
        logger.error(
            f"Failed to retrieve the number of events from ParsedEventTable for version: {version} and filename: {filename}!"
        )
        logger.exception(e)
    finally:
        session.close()
    return 0


def get_column_by_version_and_filename(
    engine, column: str, version: str, filename: str
) -> List[str]:
    Session = sessionmaker(bind=engine)
    session = Session()

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
    except SQLAlchemyError as e:
        logger.error(
            f"Failed to retrieve the {column} from ParsedEventTable for version: {version} and filename: {filename}!"
        )
        logger.exception(e)
    finally:
        session.close()
    return []


def get_parsed_events(engine: Engine, filename: str, version: str) -> List[ParsedEventTable]:
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        # Query the database for the given column with the given version and filename
        parsed_events = (
            session.query(ParsedEventTable)
            .filter(ParsedEventTable.version == version)
            .filter(ParsedEventTable.filename == filename)
            .all()
        )
        # add all parsed_events to a dictionary
        return parsed_events

    except SQLAlchemyError as e:
        logger.exception(e)
        raise e
    finally:
        session.close()

# Note to self: What relationship do our document embeddings have with the Moods?
# How do I add relationships between them so it is easy to retrieve them later?
# How can I relate them to a person's input so that I can personalize what someone sees?
def insert_parsed_event_embeddings(engine: Engine, events: List[Dict[str, str]]):
    Session = sessionmaker(bind=engine)
    session = Session()
    # Query the database for the given column with the given version and filename
    embedding_lst = []
    for parsed_event in events:
        parsed_event_embedding = ParsedEventEmbeddingsTable(
            description_embedding=parsed_event["embedding_vector"],
            embedding_version=parsed_event["version"],
            parsed_event_id=parsed_event["id"],
        )
        embedding_lst.append(parsed_event_embedding)
    try:
        session.add_all(embedding_lst)
        session.commit()
    finally:
        session.close()