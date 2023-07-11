from enum import Enum
from typing import Any, Dict, List, cast
import typer
from model.persistence_model import MoodIndex, Mood
from model.persistence_model import insert_mood
from utils.ai import EmbeddingSearch
# TODO(Sid): Filter by th Submoods, place_or_activity text
# 1. Generate embeddings for each mood and store them in a table(we don't need to train this)
# 2. Generate embeddings for each description in the drop_embedding table with the IDs from the drop table(we don't want to train these too just yet)
# 3. Filter the events by context(Assume that is present) Call this events_filtered.
# 4. Use datasette's faiss_agg query to determine the events: Demo


def index_moods(
    mood_type_to_index: MoodIndex = typer.Argument(
        ..., help="The mood type to index"
    ),
    version: str = typer.Option(
        "v1",   help="The version of the mood data to index")
):
    embedding_search = EmbeddingSearch()
    typer.echo(f"Indexing events: {mood_type_to_index.get_moods()}")
    for mood in mood_type_to_index.get_moods():
        mood = cast(Mood, mood)
        # Insert the mood into the moods table.
        # Generate the embeddings for each mood.Mood, mood.SUB_MOODS, mood.PLACES_OR_ACTIVITIES and mood.DESCRIPTIONS
        for submood in mood.SUB_MOODS:
            for place_or_activity in mood.PLACES_OR_ACTIVITIES:
                pass

def index_events():
    pass


def demo_retrieval():
    pass
