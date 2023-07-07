from dataclasses import asdict
import logging
from typing import Optional
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
            name=event.name,
            description=event.description,
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
