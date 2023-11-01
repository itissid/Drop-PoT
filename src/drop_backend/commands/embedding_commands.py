import json
import logging
from dataclasses import asdict
from enum import Enum
from typing import cast

import typer
from colorama import Fore  # type: ignore
import struct

from ..lib.ai import EmbeddingSearch
from ..model.mood_model_unsupervised import (
    Mood,
    MoodFlavors,
    generate_submoods_json_accessors,
    get_mood_json_entries,
    get_submood_embedding_text,
    insert_accessor_entries,
    insert_into_embeddings_table,
    insert_into_mood_json_table,
)
from ..model.persistence_model import (
    get_parsed_events,
    insert_parsed_event_embeddings,
)
from ..utils.cli_utils import _optionally_format_colorama, _pp

logger = logging.getLogger(__name__)


# TODO(Sid): Filter by th Submoods, place_or_activity text
# 1. Generate embeddings for each mood and store them in a table(we don't need to train this)
# 2. Generate embeddings for each description in the drop_embedding table with the IDs from the drop table(we don't want to train these too just yet)
# 3. Filter the events by context(Assume that is present) Call this events_filtered.
# 4. Use datasette's faiss_agg query to determine the events: Demo


# TODO: Override callback argument and refactor the table creation from hoboken_girl_extraction.py.
def index_moods(
    ctx: typer.Context,
    mood_type_to_index: MoodFlavors = typer.Argument(
        ...,
        help="The curated mood flavor to index(eventually generate an embedding for it)",
    ),
    version: str = typer.Option(
        "v1", help="The version of the mood data to index"
    ),
):
    typer.echo(
        f"Indexing moods: {','.join(mood.MOOD for mood in mood_type_to_index.get_moods_for_flavor())}"
    )
    for mood in mood_type_to_index.get_moods_for_flavor():
        # Insert the mood into the moods table.
        # Generate the embeddings for each mood.Mood, mood.SUB_MOODS, mood.PLACES_OR_ACTIVITIES and mood.DESCRIPTIONS
        mood = cast(Mood, mood)
        id = insert_into_mood_json_table(
            mood.MOOD,
            mood.SUB_MOODS,
            mood_type_to_index,
            version,
            ctx.obj["engine"],
        )
        insert_accessor_entries(id, mood.SUB_MOODS, ctx.obj["engine"])


class Choices(str, Enum):
    SUB_MOOD = "SUB_MOOD"
    SUB_MOOD_PLACES = "SUB_MOOD,PLACE_OR_ACTIVITY"
    SUB_MOOD_REASONNING = "SUB_MOOD,REASONING"
    SUB_MOOD_PLACES_REASONNING = "SUB_MOOD,PLACE_OR_ACTIVITY,REASONING"


# Index the moods one at a time.

# TODO: Override callback argument and refactor the table creation from hoboken_girl_extraction.py.


def index_mood_embeddings(
    ctx: typer.Context,
    mood_flavor_to_index: MoodFlavors = typer.Argument(
        ..., help="The mood type to index"
    ),
    version: str = typer.Option(
        "v1", help="The version of the mood data to index"
    ),
):
    # Generate the embeddings from the
    composite_types = [
        "SUB_MOOD",
        "SUB_MOOD,PLACE_OR_ACTIVITY",
        "SUB_MOOD,REASONING",
        "SUB_MOOD,PLACE_OR_ACTIVITY,REASONING",
    ], "Invalid composite type"
    typer.echo(
        f"Indexing for flavor({mood_flavor_to_index}): {','.join(mood.MOOD for mood in mood_flavor_to_index.get_moods_for_flavor())}"
    )
    embedding_search = EmbeddingSearch()
    for mood in mood_flavor_to_index.get_moods_for_flavor():
        indexed_moods = get_mood_json_entries(
            mood.MOOD, mood_flavor_to_index, version, ctx.obj["engine"]
        )
        assert (
            len(indexed_moods) == 1
        ), f"There should be only one mood entry, there were {len(indexed_moods)}"
        db_indexed_mood = indexed_moods[0]
        # Sanity check.
        _sanity_check_before_inserting_embeddings(
            mood.SUB_MOODS, json.loads(db_indexed_mood.sub_moods)
        )  # type: ignore
        # Dynamically generate all the embedding text.
        accessor_lst = generate_submoods_json_accessors(
            db_indexed_mood.id, mood.SUB_MOODS
        )
        # Add the embeddings.
        embedding_text_records = get_submood_embedding_text(
            db_indexed_mood, version, accessor_lst
        )
        for row in embedding_text_records:
            embedding_vector = embedding_search.fetch_embeddings(
                [row["embedding_text"]]
            )
            # datasette-fais compatible blob
            row["embedding_vector"] = encode(embedding_vector)
        insert_into_embeddings_table(ctx.obj["engine"], embedding_text_records)

def encode(vector):
    return struct.pack("f" * len(vector), *vector)


def _sanity_check_before_inserting_embeddings(sub_mood, db_indexed_submood):
    if [asdict(m) for m in sub_mood] != db_indexed_submood:
        typer.echo(
            _optionally_format_colorama(
                "Expected the submood from our file two to be equal",
                True,
                Fore.GREEN,
            )
        )
        for expected in sub_mood:
            _pp(asdict(expected))
        typer.echo(
            _optionally_format_colorama(".... to these:", True, Fore.GREEN)
        )
        for in_db in db_indexed_submood:
            _pp(asdict(in_db))
        raise ValueError(
            "The submoods from file and indexed into MoodJsonTable should be equal."
        )


class EmbeddingType(Enum):
    DESCRIPTION = "description"
    NAME_DESCRIPTION = "name_description"


def index_event_embeddings(
    ctx: typer.Context,
    embedding_types: list[EmbeddingType] = typer.Option(
        [EmbeddingType.NAME_DESCRIPTION], help="The type of embedding to index"
    ),
    filename: str = typer.Argument(
        help="The filename which is a key in the DB. Check drop.db file"
    ),
    version: str = typer.Option(
        "v1",
        help="The version of the embedding data. Just an arbitrary string.",
    ),
):
    """
    Retrieve the embeddings and the
    """
    engine = ctx.obj["engine"]
    if (
        EmbeddingType.DESCRIPTION not in embedding_types
        and EmbeddingType.NAME_DESCRIPTION not in embedding_types
    ):
        raise ValueError(
            "Expect one of description of name_description embeddings to be specified."
        )
    parsed_events = get_parsed_events(engine, filename, version)
    if len(parsed_events) == 0:
        typer.echo("No events found for given parameters.")
        return
    parsed_events_dict = [
        {
            key: value
            for key, value in event.__dict__.items()
            if not key.startswith("_")
        }
        for event in parsed_events
    ]
    embedding_search = EmbeddingSearch()
    for parsed_event in parsed_events_dict:
        # NOTE: Assume description has to be present and name is not enough to generate
        # a good enough embedding
        if parsed_event["description"]:
            event_embeddings = []

            event_description = parsed_event.get("description", "")
            event_name = parsed_event.get("name", "")
            if event_description:
                # Add a row to event_embeddings table for the description at the least.
                if EmbeddingType.DESCRIPTION in embedding_types:
                    event_embedding = {}
                    description_embedding = embedding_search.fetch_embeddings(
                        [event_description]
                    )
                    event_embedding["embedding"] = encode(description_embedding)
                    event_embedding["embedding_type"] = "description"
                    event_embedding["embedding_version"] = version
                    event_embedding["parsed_event_id"] = parsed_event["id"]
                    event_embeddings.append(event_embedding)
                if (
                    EmbeddingType.NAME_DESCRIPTION in embedding_types
                    and event_name
                ):
                    # Add a row to event_embeddings for name+description
                    event_embedding = {}
                    name_description_embedding = (
                        embedding_search.fetch_embeddings(
                            [event_name + " " + event_description]
                        )
                    )
                    event_embedding["embedding"] = encode(
                        name_description_embedding
                    )
                    event_embedding["embedding_type"] = "name_description"
                    event_embedding["embedding_version"] = version
                    event_embedding["parsed_event_id"] = parsed_event["id"]
                    event_embeddings.append(event_embedding)
            else:
                logger.debug("No description for event: %s", parsed_event["id"])
            insert_parsed_event_embeddings(engine, event_embeddings)


def demo_retrieval():
    # Select a sub mood,
    # Select a location with lat long in hoboken
    # compute distance between events and location
    #
    pass
