import json
import logging
from dataclasses import asdict, dataclass
from enum import Enum
from typing import List, Optional

from dataclasses_json import DataClassJsonMixin, dataclass_json
from model.mood_seed import GEN_Z, GEN_Z_HOBOKEN, GEN_Z_NYC, MILLENIALS
from model.types import Event
from sqlalchemy import (JSON, Column, Engine, ForeignKey, Integer, LargeBinary,
                        String, Text, UniqueConstraint, func)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

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


class ParsedEventEmbeddingsTable(Base):  # type: ignore
    __tablename__ = "parsed_events_embeddings"

    id = Column(Integer, primary_key=True)
    description_embedding = Column(LargeBinary, nullable=False)
    embedding_version = Column(String, nullable=False)

    parsed_event_id = Column(Integer, ForeignKey("parsed_events.id"))

    parsed_event = relationship("ParsedEventTable")


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


###### Mood Tables ########################################################
# See mood_seeds.py for the data.
###########################################################################


@dataclass_json
@dataclass
class SubMood:
    SUB_MOOD: str
    PLACE_OR_ACTIVITY: List[str]
    REASONING: str


@dataclass_json
@dataclass
class Mood(DataClassJsonMixin):
    MOOD: str
    SUB_MOODS: List[SubMood]


class MoodIndex(str, Enum):
    GEN_Z_HOBOKEN = "GEN_Z_HOBOKEN"
    MILLENIALS = "MILLENIALS"
    GEN_Z = "GEN_Z"
    GEN_Z_NYC = "GEN_Z_NYC"

    def get_moods(self) -> List[Mood]:
        selected = None
        if self == MoodIndex.GEN_Z_HOBOKEN:
            selected = GEN_Z_HOBOKEN
        elif self == MoodIndex.MILLENIALS:
            selected = MILLENIALS
        elif self == MoodIndex.GEN_Z:
            selected = GEN_Z
        elif self == MoodIndex.GEN_Z_NYC:
            selected = GEN_Z_NYC
        return [Mood.from_dict(i) for i in selected] if selected else None


class MoodJsonTable(Base):  # type: ignore
    __tablename__ = "MoodJsonTable"

    id = Column(Integer, primary_key=True)
    mood = Column(String, nullable=False)
    # This field will store serialized list of Moods
    moods = Column(Text, nullable=False)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)

    # Relationship to SubMoodsTable
    submoods = relationship("SubMoodsTable", back_populates="mood")


class SubMoodsTable(Base):  # type: ignore
    __tablename__ = "SubMoodsTable"

    id = Column(Integer, primary_key=True)
    submood_json_path = Column(String, nullable=False)
    mood_id_ref = Column(Integer, ForeignKey("MoodJsonTable.id"))
    composite_type = Column(String, nullable=False)
    # This field will store serialized list of json paths
    json_path_arr = Column(Text, nullable=False)

    # Relationship to MoodJsonTable
    mood = relationship("MoodJsonTable", back_populates="submoods")

    # Relationship to SubmoodBasedEmbeddingsTable
    embedding = relationship(
        "SubmoodBasedEmbeddingsTable", uselist=False, back_populates="submood"
    )


class SubmoodBasedEmbeddingsTable(Base):  # type: ignore
    __tablename__ = "SubmoodBasedEmbeddingsTable"

    id = Column(Integer, primary_key=True)
    submood_id = Column(Integer, ForeignKey("SubMoodsTable.id"))
    embedding = Column(LargeBinary)

    # Relationship to SubMoodsTable
    submood = relationship("SubMoodsTable", back_populates="embedding")


def insert_into_mood_json_table(
    mood: str, moods: List[Mood], name: str, version: str, engine: Engine
):
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        moods_dict = [asdict(m) for m in moods]
        mood_json_table_entry = MoodJsonTable(
            mood=mood,
            moods=json.dumps(moods_dict),  # Convert moods to serialized form
            name=name,
            version=version,
        )
        session.add(mood_json_table_entry)
        session.commit()
        return mood_json_table_entry.id

    finally:
        session.close()


def insert_into_submoods_table(mood_id, submoods, engine):
    pass


def _generate_submoods_entries(mood_id, submoods):
    entries = []
    for idx, submood in enumerate(submoods):
        json_path_base = f"$.SUB_MOODS[{idx}].SUB_MOOD"
        submood_entry = SubMoodsTable(
            submood_json_path=json_path_base,
            mood_id_ref=mood_id,
            composite_type="SUB_MOOD",
        )
        entries.append(submood_entry)

        for i in range(len(submood.PLACE_OR_ACTIVITY)):
            json_path = (
                f"{json_path_base}, $.SUB_MOODS[{idx}].PLACE_OR_ACTIVITY[{i}]"
            )
            submood_entry = SubMoodsTable(
                submood_json_path=json_path,
                mood_id_ref=mood_id,
                composite_type="SUB_MOOD,PLACE_OR_ACTIVITY",
            )
            entries.append(submood_entry)

        json_path = f"{json_path_base}, $.SUB_MOODS[{idx}].REASONING"
        submood_entry = SubMoodsTable(
            submood_json_path=json_path,
            mood_id_ref=mood_id,
            composite_type="SUB_MOOD,PLACE_OR_ACTIVITY,REASONING",
        )
        entries.append(submood_entry)

    return entries


def _insert_submoods_entries(entries, engine):
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        session.add_all(entries)
        session.commit()

    finally:
        session.close()
