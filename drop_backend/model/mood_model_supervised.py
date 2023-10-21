import logging

from sqlalchemy import Column, ForeignKey, Integer, Text, and_
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound

from ..types.mood_submood import SubMood
from ..utils.db_utils import session_manager
from .merge_base import Base

logger = logging.getLogger(__name__)


class MoodSubmoodTable(Base):  # type: ignore
    __tablename__ = "MoodSubMoodTable"
    id = Column(
        Integer, primary_key=True, autoincrement=True
    )  # Unique for the pair of mood submood
    mood = Column(Text, nullable=False)
    submood = Column(Text, nullable=False)


class SubMoodEventTable(Base):  # type: ignore
    __tablename__ = "SubMoodEventTable"
    event_id = Column(Integer, ForeignKey("parsed_events.id"), primary_key=True)
    mood_sub_mood_id = Column(
        Integer, ForeignKey("MoodSubMoodTable.id"), primary_key=True
    )
    complete_json = Column(
        Text, nullable=False
    )  # Stores the actual json response from ai.

    parsed_events = relationship(  # type: ignore
        "ParsedEventTable", back_populates="sub_mood_event"
    )


@session_manager
def handle_mood_submood(session, mood: str, sub_mood: str) -> int:
    # Ensure mood and sub_mood are not null/empty
    if not mood or not sub_mood:
        error_msg = "Mood and Sub-mood cannot be null or empty"
        logger.error(error_msg)  # Assuming logger is available in this scope
        raise ValueError(error_msg)

    try:
        # Try to find an existing entry with the given mood and sub_mood
        entry = (
            session.query(MoodSubmoodTable)
            .filter(
                and_(
                    MoodSubmoodTable.mood == mood,
                    MoodSubmoodTable.submood == sub_mood,
                )
            )
            .one()
        )
    except NoResultFound:
        # If not found, create a new entry
        entry = MoodSubmoodTable(mood=mood, submood=sub_mood)
        session.add(entry)
        session.flush()  # To ensure the entry is assigned an ID before the session is committed by the decorator

    # At this point, entry should either be the found or newly created entry, and should have an ID.
    return entry.id


@session_manager
def handle_sub_mood_event(
    session, sub_mood_item: SubMood, mood_sub_mood_entry: int
) -> None:
    # For each event, insert into SubMoodEventTable
    for event in sub_mood_item.EVENTS:
        event_id = int(
            event.replace("Event", "")
        )  # Extracting ID from "EventX"
        complete_json = sub_mood_item.model_dump_json()

        sub_mood_event_entry = SubMoodEventTable(
            event_id=event_id,
            mood_sub_mood_id=mood_sub_mood_entry,
            complete_json=complete_json,
        )
        session.add(sub_mood_event_entry)
    session.commit()
