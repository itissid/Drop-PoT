from sqlalchemy import MetaData

from main.model.mood_model import Base as MoodBase
from main.model.persistence_model import Base as PersistenceBase


def merge_metadata(*original_metadata) -> MetaData:
    merged = MetaData()

    for original_metadatum in original_metadata:
        for table in original_metadatum.tables.values():
            table.to_metadata(merged)

    return merged


combined_meta_data = merge_metadata(
    MoodBase.metadata, PersistenceBase.metadata
)
