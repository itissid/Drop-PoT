
from pydantic import BaseModel, create_model
from drop_backend.types.city_event import CityEvent
from drop_backend.model.ai_conv_types import EventNode

CityEventEventNode = create_model(
    'CityEventModel',
    event_obj=(CityEvent, None),
    __base__=EventNode,
)
