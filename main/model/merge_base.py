from sqlalchemy import MetaData

from main.model.mood_model_unsupervised import Base as MoodBaseUnsupervised
from main.model.mood_model_supervised import Base as MoodBaseSupervised
from main.model.persistence_model import Base as PersistenceBase


def merge_metadata(*original_metadata) -> MetaData:
    merged = MetaData()

    for original_metadatum in original_metadata:
        for table in original_metadatum.tables.values():
            table.to_metadata(merged)

    return merged


combined_meta_data = merge_metadata(
    MoodBaseUnsupervised.metadata,
    PersistenceBase.metadata,
    MoodBaseSupervised.metadata,
)
