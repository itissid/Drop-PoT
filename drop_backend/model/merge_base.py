from sqlalchemy import MetaData

from .mood_model_unsupervised import Base as MoodBaseUnsupervised
from .mood_model_supervised import Base as MoodBaseSupervised
from .persistence_model import Base as PersistenceBase


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
