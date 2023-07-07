from dataclasses import asdict
import logging
from typing import List, Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
from model.types import Event

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


def add_event(
    engine,
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
