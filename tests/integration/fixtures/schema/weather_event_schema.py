
# Generated code. Don't change this file unless you know what you are doing.
from drop_backend.lib.config_generator import validate_schema

@validate_schema("WeatherEvent", "tests.integration.fixtures")
def weather_event_json_schema():
    return """{
  "$defs": {
    "Unit": {
      "enum": [
        "celsius",
        "fahrenheit"
      ],
      "title": "Unit",
      "type": "string"
    }
  },
  "additionalProperties": false,
  "properties": {
    "location": {
      "title": "Location",
      "type": "string"
    },
    "temperature": {
      "title": "Temperature",
      "type": "integer"
    },
    "unit": {
      "$ref": "#/$defs/Unit"
    }
  },
  "required": [
    "location",
    "temperature",
    "unit"
  ],
  "title": "WeatherEvent",
  "type": "object"
}"""
    
# Generated code. Don't change this file unless you know what you are doing.
import json
from typing import Tuple, List


from drop_backend.model.ai_conv_types import (
    OpenAIFunctionCallSpec, UserExplicitFunctionCall
)

def weather_event_function_call_param() -> Tuple[List[OpenAIFunctionCallSpec], UserExplicitFunctionCall]:
    json_schema_weather_event = weather_event_json_schema()
    params = {"parameters": json.loads(json_schema_weather_event)}
    return (
        [
            OpenAIFunctionCallSpec(
                name= "get_current_weather",
                description = "Parse the data into a WeatherEvent object",
                **params,
            )
        ],
        # TODO: Also support "auto" and "none"
        UserExplicitFunctionCall(name="get_current_weather"),
    )
