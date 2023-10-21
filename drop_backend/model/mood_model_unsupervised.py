###### Mood Tables ########################################################
# See mood_seeds.py for the data.
###########################################################################


import json
import logging
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, List

from dataclasses_json import DataClassJsonMixin, dataclass_json
from jsonpath_ng import parse  # type: ignore
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    and_,
)
from .merge_base import Base
from sqlalchemy.orm import sessionmaker

from .mood_seed import GEN_Z, GEN_Z_HOBOKEN, GEN_Z_NYC, MILLENIALS

logger = logging.getLogger(__name__)


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


class MoodFlavors(str, Enum):
    GEN_Z_HOBOKEN = "GEN_Z_HOBOKEN"
    MILLENIALS = "MILLENIALS"
    GEN_Z = "GEN_Z"
    GEN_Z_NYC = "GEN_Z_NYC"

    def get_moods_for_flavor(self) -> List[Mood]:
        selected = None
        if self == MoodFlavors.GEN_Z_HOBOKEN:
            selected = GEN_Z_HOBOKEN
        elif self == MoodFlavors.MILLENIALS:
            selected = MILLENIALS
        elif self == MoodFlavors.GEN_Z:
            selected = GEN_Z
        elif self == MoodFlavors.GEN_Z_NYC:
            selected = GEN_Z_NYC
        else:
            raise ValueError(
                f"New MoodFlavors: {self} added, but not implemented!"
            )
        return [Mood.from_dict(i) for i in selected]


###########################
###### OLDER TABLES #######
class MoodJsonTable(Base):  # type: ignore
    __tablename__ = "MoodJsonTable"

    id = Column(Integer, primary_key=True)
    mood = Column(String, nullable=False)
    # This field will store serialized list of Moods
    sub_moods = Column(Text, nullable=False)
    flavor = Column(String, nullable=False)
    version = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("mood", "flavor", "version", name="mood_name_version"),
    )


class SubmoodBasedEmbeddingTextAccessorTable(Base):  # type: ignore
    """
    Just a convenience table to look at the accessors.
    See insert_submoods_entries for details.
    """

    __tablename__ = "SubmoodBasedEmbeddingTextAccessorTable"

    id = Column(Integer, primary_key=True)
    submood_accessor_json_path = Column(String, nullable=False)
    embedding_accessor_json_path = Column(String, nullable=False)
    mood_id_ref = Column(Integer, ForeignKey("MoodJsonTable.id"))
    composite_type = Column(String, nullable=False)


class SubmoodBasedEmbeddingsTable(Base):  # type: ignore
    __tablename__ = "SubmoodBasedEmbeddingsTable"

    id = Column(Integer, primary_key=True)
    mood_id = Column(Integer, ForeignKey("MoodJsonTable.id"))
    version = Column(String, nullable=False)
    # The string key from the sub_moods json field of MoodJsonTable
    sub_mood = Column(String, nullable=False)
    embedding_text = Column(Text, nullable=False)
    embedding_text_composite_type = Column(String, nullable=False)
    embedding_vector = Column(LargeBinary)
    __table_args__ = (
        UniqueConstraint(
            "mood_id",
            "sub_mood",
            "embedding_text_composite_type",
            "version",
            name="mood_submood_composite_version",
        ),
    )


def insert_into_mood_json_table(
    mood: str,
    sub_moods: List[SubMood],
    flavor: MoodFlavors,
    version: str,
    engine: Any,
):
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        sub_moods_dict = [asdict(m) for m in sub_moods]
        # Search if mood, sub_moods, flavor, version combination already exists
        record = (
            session.query(MoodJsonTable)
            .filter(
                and_(
                    MoodJsonTable.mood == mood,
                    MoodJsonTable.sub_moods == json.dumps(sub_moods_dict),
                    MoodJsonTable.flavor == flavor,
                    MoodJsonTable.version == version,
                )
            )
            .one_or_none()
        )

        # If it does not exist, create new entry
        if not record:
            mood_json_table_entry = MoodJsonTable(
                mood=mood,
                sub_moods=json.dumps(sub_moods_dict),
                flavor=flavor,
                version=version,
            )
            session.add(mood_json_table_entry)
            session.commit()
            return mood_json_table_entry.id
        else:
            logger.warning(
                "Already found record in MoodJsonTable for %d", record.id
            )
            return record.id
    finally:
        session.close()


def get_mood_json_entries(
    mood: str, flavor: MoodFlavors, version: str, engine
) -> List[MoodJsonTable]:
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        records = (
            session.query(MoodJsonTable)
            .filter(
                and_(
                    MoodJsonTable.mood == mood,
                    MoodJsonTable.flavor == flavor,
                    MoodJsonTable.version == version,
                )
            )
            .all()
        )
        return records
    finally:
        session.close()


def insert_accessor_entries(mood_id: int, submoods: List[SubMood], engine):
    entries = generate_submoods_json_accessors(mood_id, submoods)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        session.add_all(entries)
        session.commit()

    finally:
        session.close()


def generate_submoods_json_accessors(
    mood_id, submoods: List[SubMood]
) -> List[SubmoodBasedEmbeddingTextAccessorTable]:
    """
    Instead of hardcoding the strings of GEN_Z_HOBOKEN this will help make a table like:
    ```
    "[
            {
                "SUB_MOOD": "City Exploration",
                "PLACE_OR_ACTIVITY": [
                    "Biking on the Hudson River Waterfront Walkway",
                    "Exploring murals in Jersey City",
                ],
                "REASONING": "Gen Z's curiosity extends to exploring their hometowns of Hoboken and Jersey City. From biking along scenic routes to exploring vibrant street art, there's plenty to discover. ",
            },
            {
                "SUB_MOOD": "Thrill-Seeking",
                "PLACE_OR_ACTIVITY": [
                    "Kayaking on the Hudson",
                    "Escape Room challenges in Jersey City",
                ],
                "REASONING": "Gen Z seeks adventure and thrills, even within city bounds. Activities like kayaking and escape rooms offer an exciting break from routine. ",
            },
        ]
    ```

    `id, submood_accessor_json_path, embedding_accessor_json_path, mood_id_ref, composite_type`
    1, "$[0].SUBMOOD", "$[0].SUBMOOD", 0, "SUBMOOD", NULL
    2,  "$[1].SUBMOOD", "$[1].SUBMOOD", 0, "SUBMOOD", NULL
    3, "$[0].SUBMOOD", "'[$[0].SUBMOOD, $.SUB_MOODS[0].PLACE_OR_ACTIVITY[0], $.SUB_MOODS[0].PLACE_OR_ACTIVITY[1]]", 0, "SUBMOOD,PLACE_OR_ACTIVITY",  '
    ...
    6. "$[1].SUBMOOD", "'$[1].SUBMOOD, $[0].PLACE_OR_ACTIVITY[0]', '$[0].PLACE_OR_ACTIVITY[1]', '$[0].SUBMOOD.REASONING'" , 0, "SUBMOOD,PLACE_OR_ACTIVITY,REASONING", '

    TODO(Sid): Move the logic for the JSON paths to be a SubMood class's static method.
    """
    entries = []
    for idx, submood in enumerate(submoods):
        json_path_base = f"$[{idx}].SUB_MOOD"
        submood_entry = SubmoodBasedEmbeddingTextAccessorTable(
            submood_accessor_json_path=f"$[{idx}].SUB_MOOD",
            embedding_accessor_json_path=json_path_base,
            mood_id_ref=mood_id,
            composite_type="SUB_MOOD",
        )
        entries.append(submood_entry)

        submood_place_act = []
        for i in range(len(submood.PLACE_OR_ACTIVITY)):
            submood_place_act.append(f"$[{idx}].PLACE_OR_ACTIVITY[{i}]")
        json_path = f"{json_path_base}, {','.join(submood_place_act)}"
        submood_entry = SubmoodBasedEmbeddingTextAccessorTable(
            submood_accessor_json_path=f"$[{idx}].SUB_MOOD",
            embedding_accessor_json_path=json_path,
            mood_id_ref=mood_id,
            composite_type="SUB_MOOD,PLACE_OR_ACTIVITY",
        )
        entries.append(submood_entry)

        json_path = f"{json_path_base}, {','.join(submood_place_act)},$[{idx}].REASONING"
        submood_entry = SubmoodBasedEmbeddingTextAccessorTable(
            submood_accessor_json_path=f"$[{idx}].SUB_MOOD",
            embedding_accessor_json_path=json_path,
            mood_id_ref=mood_id,
            composite_type="SUB_MOOD,PLACE_OR_ACTIVITY,REASONING",
        )
        entries.append(submood_entry)

        json_path = f"{json_path_base},$[{idx}].REASONING"
        submood_entry = SubmoodBasedEmbeddingTextAccessorTable(
            submood_accessor_json_path=f"$[{idx}].SUB_MOOD",
            embedding_accessor_json_path=json_path,
            mood_id_ref=mood_id,
            composite_type="SUB_MOOD,REASONING",
        )
        entries.append(submood_entry)

    return entries


def get_submood_embedding_text(
    mood: MoodJsonTable,
    version: str,
    json_path_records: List[SubmoodBasedEmbeddingTextAccessorTable],
):
    sub_moods_json = json.loads(mood.sub_moods)
    records = []
    for path_record in json_path_records:
        sub_mood_expr = parse(path_record.submood_accessor_json_path)
        embedding_text_exprs = [
            parse(i.strip())
            for i in path_record.embedding_accessor_json_path.split(",")
        ]
        assert len(embedding_text_exprs) > 0
        # Match the JSONPath to get the sub_mood and embedding_text
        sub_mood_lst = [
            match.value for match in sub_mood_expr.find(sub_moods_json)
        ]
        assert (
            len(sub_mood_lst) == 1
        ), f"Expected to find exactly one sub_mood for {path_record.submood_accessor_json_path} but found {len(sub_mood_lst)}"
        embedding_text_parts = []
        for embedding_text_expr in embedding_text_exprs:
            embedding_text_lst = [
                match.value
                for match in embedding_text_expr.find(sub_moods_json)
            ]
            assert (
                len(embedding_text_lst) == 1
            ), f"Expected to find exactly one embedding_text for {path_record.embedding_accessor_json_path} but found {len(embedding_text_lst)}"
            embedding_text_parts.append(embedding_text_lst[0])
        records.append(
            dict(
                mood_id=path_record.mood_id_ref,
                version=version,
                sub_mood=sub_mood_lst[0],
                embedding_text_composite_type=path_record.composite_type,
                embedding_text=". ".join(embedding_text_parts),
            )
        )

    return records


def insert_into_embeddings_table(engine, embedding_entries: List[dict]):
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        for entry in embedding_entries:
            record = (
                session.query(SubmoodBasedEmbeddingsTable)
                .filter(
                    SubmoodBasedEmbeddingsTable.mood_id == entry["mood_id"],
                    SubmoodBasedEmbeddingsTable.version == entry["version"],
                    SubmoodBasedEmbeddingsTable.sub_mood == entry["sub_mood"],
                    SubmoodBasedEmbeddingsTable.embedding_text_composite_type
                    == entry["embedding_text_composite_type"],
                )
                .first()
            )
            # Only create a new entry if no record is found
            if not record:
                embeddings_table_entry = SubmoodBasedEmbeddingsTable(
                    mood_id=entry["mood_id"],
                    version=entry["version"],
                    sub_mood=entry["sub_mood"],
                    embedding_text_composite_type=entry[
                        "embedding_text_composite_type"
                    ],
                    embedding_text=entry["embedding_text"],
                    embedding_vector=entry["embedding_vector"],
                )
                session.add(embeddings_table_entry)
        session.commit()
    except Exception as exp:
        session.rollback()
        raise exp
    finally:
        session.close()
