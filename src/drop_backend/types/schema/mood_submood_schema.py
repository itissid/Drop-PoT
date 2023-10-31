
# Generated code. Don't change this file unless you know what you are doing.
from drop_backend.lib.config_generator import validate_schema

@validate_schema("MoodSubmood", "drop_backend.types")
def mood_submood_json_schema():
    return """{
  "$defs": {
    "SubMood": {
      "additionalProperties": false,
      "properties": {
        "SUB_MOOD": {
          "title": "Sub Mood",
          "type": "string"
        },
        "DEMOGRAPHICS": {
          "items": {
            "type": "string"
          },
          "title": "Demographics",
          "type": "array"
        },
        "EVENTS": {
          "description": "Must be in the format `Event<NUMBER>` as specified in the input.",
          "items": {
            "type": "string"
          },
          "title": "Events",
          "type": "array"
        },
        "REASONING": {
          "title": "Reasoning",
          "type": "string"
        }
      },
      "required": [
        "SUB_MOOD",
        "DEMOGRAPHICS",
        "REASONING"
      ],
      "title": "SubMood",
      "type": "object"
    },
    "_MoodSubmood": {
      "additionalProperties": false,
      "properties": {
        "MOOD": {
          "title": "Mood",
          "type": "string"
        },
        "SUB_MOODS": {
          "items": {
            "$ref": "#/$defs/SubMood"
          },
          "title": "Sub Moods",
          "type": "array"
        }
      },
      "required": [
        "MOOD",
        "SUB_MOODS"
      ],
      "title": "_MoodSubmood",
      "type": "object"
    }
  },
  "properties": {
    "MOODS": {
      "items": {
        "$ref": "#/$defs/_MoodSubmood"
      },
      "title": "Moods",
      "type": "array"
    }
  },
  "required": [
    "MOODS"
  ],
  "title": "MoodSubmood",
  "type": "object"
}"""
    
# Generated code. Don't change this file unless you know what you are doing.
import json
from typing import Tuple, List


from drop_backend.model.ai_conv_types import (
    OpenAIFunctionCallSpec, UserExplicitFunctionCall
)

def mood_submood_function_call_param() -> Tuple[List[OpenAIFunctionCallSpec], UserExplicitFunctionCall]:
    json_schema_mood_submood = mood_submood_json_schema()
    params = {"parameters": json.loads(json_schema_mood_submood)}
    return (
        [
            OpenAIFunctionCallSpec(
                name= "create_mood_submood",
                description = "Parse the data into a MoodSubmood object",
                **params,
            )
        ],
        # TODO: Also support "auto" and "none"
        UserExplicitFunctionCall(name="create_mood_submood"),
    )
