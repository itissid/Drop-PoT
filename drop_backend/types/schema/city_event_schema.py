
# Generated code. Don't change this file unless you know what you are doing.
from drop_backend.lib.config_generator import validate_schema

@validate_schema("CityEvent", "drop_backend.types")
def city_event_json_schema():
    return """{
  "$defs": {
    "PaymentMode": {
      "enum": [
        "ticket",
        "paid_membership",
        "appointment",
        "in_premises"
      ],
      "title": "PaymentMode",
      "type": "string"
    }
  },
  "additionalProperties": false,
  "properties": {
    "name": {
      "title": "Name",
      "type": "string"
    },
    "description": {
      "title": "Description",
      "type": "string"
    },
    "categories": {
      "items": {},
      "title": "Categories",
      "type": "array"
    },
    "addresses": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Addresses"
    },
    "is_ongoing": {
      "default": false,
      "title": "Is Ongoing",
      "type": "boolean"
    },
    "start_date": {
      "anyOf": [
        {
          "items": {
            "format": "date",
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Start Date"
    },
    "end_date": {
      "anyOf": [
        {
          "items": {
            "format": "date",
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "End Date"
    },
    "start_time": {
      "anyOf": [
        {
          "items": {
            "format": "time",
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Start Time"
    },
    "end_time": {
      "anyOf": [
        {
          "items": {
            "format": "time",
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "End Time"
    },
    "is_paid": {
      "default": false,
      "title": "Is Paid",
      "type": "boolean"
    },
    "has_promotion": {
      "default": false,
      "title": "Has Promotion",
      "type": "boolean"
    },
    "promotion_details": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Promotion Details"
    },
    "payment_mode": {
      "anyOf": [
        {
          "$ref": "#/$defs/PaymentMode"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "payment_details": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Payment Details"
    },
    "links": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Links"
    }
  },
  "required": [
    "name",
    "description",
    "categories"
  ],
  "title": "CityEvent",
  "type": "object"
}"""
    
# Generated code. Don't change this file unless you know what you are doing.
import json
from typing import List, Tuple


from drop_backend.model.ai_conv_types import (
    OpenAIFunctionCallSpec, UserExplicitFunctionCall
)

def city_event_function_call_param() -> Tuple[List[OpenAIFunctionCallSpec], UserExplicitFunctionCall]:
    json_schema_city_event = city_event_json_schema()
    params = {"parameters": json.loads(json_schema_city_event)}
    return (
        [
            OpenAIFunctionCallSpec(
                name= "create_city_event",
                description = "Parse the data into a CityEvent object",
                **params,
            )
        ],
        UserExplicitFunctionCall(name="create_city_event"),
    )
