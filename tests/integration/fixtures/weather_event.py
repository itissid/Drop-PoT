# make a pydantic class for the weather example in open ai
# Use command from the main directlru
# (drop-py3.9) sid@Sids-MBP:~/workspace/drop$ PYTHONPATH=".:src/:tests/" \
#       python -m drop_backend.commands config-generator-commands gen-model-code-bindings \
#       WeatherEvent --schema-directory-prefix tests/integration/fixtures/schema/ \
#       --type-module-prefix tests.integration.fixtures
# Note that we need to add src, tests to the PYTHONPATH to make sure that those are
# discoverable to the config generator code. Like even pytest also relies on the PYTHONPATH in pytest.ini
# so this is not hackish.
import enum

from pydantic import BaseModel, ConfigDict

from drop_backend.types.base import CreatorBase


# pylint: disable=invalid-name
class Unit(enum.Enum):
    celsius = "celsius"
    fahrenheit = "fahrenheit"


class WeatherEvent(BaseModel, CreatorBase):
    model_config = ConfigDict(extra="forbid")
    location: str
    temperature: int
    unit: Unit

    @classmethod
    def create(cls, function_name: str, **kwargs):  # type: ignore[override]
        if function_name == cls.default_fn_name():
            return WeatherEvent(**kwargs)
        else:
            raise AttributeError(
                f"Function {function_name} not supported for {cls.__name__}"
            )

    @classmethod
    def default_fn_name(cls) -> str:  # type: ignore[override]
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
