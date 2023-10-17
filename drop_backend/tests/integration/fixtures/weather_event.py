# make a pydantic class for the weather example in open ai
import enum

from pydantic import BaseModel, ConfigDict

from drop_backend.types.base import CreatorBase


class Unit(enum.Enum):
    celsius = "celsius"
    fahrenheit = "fahrenheit"


#
class WeatherEvent(BaseModel, CreatorBase):
    model_config = ConfigDict(extra="forbid")
    location: str
    temperature: int
    unit: Unit

    @classmethod
    def create(cls, function_name: str, **kwargs):
        if function_name == cls.default_fn_name():
            #     weather_info = {
            #         "location": location,
            #         "temperature": ...,
            #         "unit": unit,
            #         "forecast": ["sunny", "windy"],
            #     }
            return WeatherEvent(**kwargs)
        else:
            raise AttributeError(
                f"Function {function_name} not supported for {cls.__name__}"
            )

    @classmethod
    def default_fn_name(cls) -> str:
        return "get_current_weather"
    
    def __eq__(self, other):
        if not other:
            return False
        if not isinstance(other, WeatherEvent):
            return False
        if id(self) == id(other):
            return True
        return (
            self.location == other.location
            and self.temperature == other.temperature
            and self.unit.value == other.unit.value
        )
