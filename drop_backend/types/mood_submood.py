from typing import Annotated, List

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from drop_backend.types.base import CreatorBase


def check_event_name(event_name: str) -> str:
    assert (
        event_name.startswith("Event")
        and event_name.split("Event")[1].isdigit()
    )
    return event_name


_EventID = Annotated[str, AfterValidator(check_event_name)]


class SubMood(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    SUB_MOOD: str
    DEMOGRAPHICS: list[str]
    EVENTS: list[_EventID] = Field(
        default_factory=list,
        validation_alias="PLACE_OR_ACTIVITY",  # Accept the old type name from the unsupervised mood gen code.
        description="Must be in the format `Event<NUMBER>` as specified in the input.",
    )
    REASONING: str


class _MoodSubmood(BaseModel):
    model_config = ConfigDict(extra="forbid")
    """
    A pydantic model looks like for a collection of events:
    {"MOOD": "Music & Culture",
        "SUB_MOODS": [
            {
                "SUB_MOOD": "Concert Vibes",
                "DEMOGRAPHICS": ["GenZ"],
                "EVENTS": [ "Event1", "Event2" ],
                "REASONING": "Just like their NYC counterparts, Gen Z, Millenials in Hoboken and Jersey City enjoy live music experiences. Local venues and events offer a variety of such opportunities. ",
            },
            {
                "SUB_MOOD": "Cultural Exploration",
                "DEMOGRAPHICS": ["GenZ", "Millenials"],
                "EVENTS": [ "Event3", "Event4" ],
                "REASONING": "Hoboken and Jersey City are rich in culture and arts. Gen Z takes interest in exploring local art scenes and historical places. ",
            },
            {
                "SUB_MOOD": "Family Time",
                "DEMOGRAPHICS": ["Millenials"],
                "EVENTS": [ "Event5"],
                "REASONING": "Hoboken and Jersey City are young but also have families. Millenials are more likely to be interested in children events.",
            },
        ]
    }
    """

    MOOD: str
    SUB_MOODS: list[SubMood]


class MoodSubmood(BaseModel, CreatorBase):
    MOODS: List[_MoodSubmood]

    @classmethod
    def create(cls, function_name: str, **kwargs) -> "MoodSubmood":  # type: ignore[override]
        if function_name == cls.default_fn_name():
            return MoodSubmood.model_validate(kwargs, strict=True)
        else:
            raise AttributeError(
                f"Function {function_name} not supported for {cls.__name__}"
            )

    @classmethod
    def default_fn_name(cls) -> str:  # type: ignore[override]
        return "create_mood_submood"
