import typing
from typing import List, Tuple

from main.model.ai_conv_types import OpenAIFunctionCallParameters
from main.model.ai_conv_types import OpenAIFunctionCallProperty as p
from main.model.ai_conv_types import (
    OpenAIFunctionCallSpec,
    UserExplicitFunctionCall,
)

# def mood_submood_function_param_spec() -> List[OpenAIFunctionCallSpec]:
#     return [OpenAIFunctionCallSpec(
#     name = "create_mood_submood_from_events",
#     description = "Create a mood and submood from the provided event string",
#     parameters=OpenAIFunctionCallParameters(
#         type = "array",
#         properties={
#             "type": "object",
#             "properties": {
#                 "MOOD": {
#                     "type": "string"
#                 },
#                 "SUB_MOODS": {
#                     "type": "array",
#                     "items": {
#                         "type": "object",
#                         "properties": {
#                             "SUB_MOOD": {
#                                 "type": "string"
#                             },
#                             "DEMOGRAPHICS": {
#                                 "type": "array",
#                                 "items": {
#                                     "type": "string"
#                                 }
#                             },
#                             "PLACE_OR_ACTIVITY": {
#                                 "type": "array",
#                                 "items": {
#                                     "type": "string"
#                                 }
#                             },
#                             "REASONING": {
#                                 "type": "string"
#                             },
#                             "EVENTS": {
#                                 "type": "array",
#                                 "items": {
#                                     "type": "string"
#                                 }
#                             }
#                         },
#                         "required": [
#                             "DEMOGRAPHICS",
#                             "REASONING",
#                             "SUB_MOOD"
#                         ]
#                     }
#                 }
#             },
#             "required": [
#                 "MOOD",
#                 "SUB_MOODS"
#             ]
#         }
# })]

# Control the function generation
config = {
    "json_example": {},  # To generate json schema
    "model_location_package": "main.model",  # Change this to some where pydantic/dataclass model will be generated in.
    # Function returns object of desired type and a string representing the function call itself for replay, like:
    # "called_fn(arg1, arg2,.... kwarg1="...", kwarg2="...")"
    # One return type will be the model generated above. Once the type is generated, along
    # side will need to be
    #
    # TODO: Support user generated types with a plugin model.
    "function_for_ai_response": lambda message_node: None,  # passed through to aidriver.
    # If the events flag is set then the function is attached to the user message to AI
    # I can probably have a library wrapper to do this.
    # If the interrogation flag is attached.
    "apply_function_call_to": ["events", "interrogation"],
    # The interrogation class is set up with this flag and the function.
    "interrogation_class": "InterrogationClass reference",
}

# Json(part of config) -> Json schema. Json Schema -> Pydantic model generation
# Json Schema goes into OpenAPI function call spec, we don't have to describe it here.
# Then there is a function that needs to be called also part of config
# Some unknowns:
# How to make sure the types are correct in the generated JSON schema? And further in pydantic model.
# This means I need to have the pydantic model geneterated(it cannot only be dynamic) so I can debug it.
#


def hoboken_girl_event_function_param_spec() -> List[OpenAIFunctionCallSpec]:
    return [
        OpenAIFunctionCallSpec(
            name="create_event",
            description="Parse an event's fields from the provided text",
            parameters=OpenAIFunctionCallParameters(
                type="object",
                properties={
                    "name": p(
                        type="string",
                    ),
                    "description": p(
                        type="string",
                    ),
                    "categories": p(
                        type="array",
                        items=p(type="string"),
                    ),
                    "addresses": p(
                        type="array",
                        items=p(
                            type="string",
                        ),
                    ),
                    "is_ongoing": p(
                        type="boolean",
                    ),
                    "start_date": p(
                        type="array",
                        items=p(
                            type="string",
                        ),
                    ),
                    "end_date": p(
                        type="array",
                        items=p(
                            type="string",
                        ),
                    ),
                    "start_time": p(
                        type="array",
                        items=p(
                            type="string",
                        ),
                    ),
                    "end_time": p(
                        type="array",
                        items=p(
                            type="string",
                        ),
                    ),
                    "is_paid": p(
                        type="boolean",
                    ),
                    "has_promotion": p(
                        type="boolean",
                    ),
                    "promotion_details": p(
                        type="string",
                    ),
                    "payment_mode": p(
                        type="string",
                        enum=[
                            "ticket",
                            "paid_membership",
                            "appointment",
                            "in_premises",
                        ],
                    ),
                    "payment_details": p(
                        type="string",
                    ),
                    "links": p(
                        type="array",
                        items=p(type="string"),
                    ),
                },
                required=["name", "description", "categories"],
            ),
        )
    ]


def hoboken_girl_event_function_param() -> (
    Tuple[List[OpenAIFunctionCallSpec], UserExplicitFunctionCall]
):
    # return hoboken_girl_event_function_param_spec(), UserExplicitFunctionCall(name="create_event")
    import json

    return (
        json.loads(
            """[
    {

        "name": "create_event",
        "description": "Parse an event's fields from the provided text",
        "parameters": {
            "$defs": {
                "PaymentMode": {
                "enum": [
                    1,
                    2,
                    3,
                    4
                ],
                "title": "PaymentMode",
                "type": "integer"
                }
            },
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
            "title": "Event",
            "type": "object"
        }
    }]
    """
        ),
        UserExplicitFunctionCall(name="create_event"),
    )
    # return [{
    #         "name": "create_event",
    #         "description": "Parse an event's fields from the provided text",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "name": {
    #                     "type": "string",
    #                 },
    #                 "description": {
    #                     "type": "string",
    #                 },
    #                 "categories": {
    #                     "type": "array",
    #                     "items": {"type": "string"},
    #                 },
    #                 "addresses": {
    #                     "type": "array",
    #                     "items": {"type": "string"},
    #                 },
    #                 "is_ongoing": {
    #                     "type": "boolean",
    #                 },
    #                 "start_date": {
    #                     "type": "array",
    #                     "items": {"type": "string"},
    #                 },
    #                 "end_date": {
    #                     "type": "array",
    #                     "items": {"type": "string"},
    #                 },
    #                 "start_time": {
    #                     "type": "array",
    #                     "items": {"type": "string"},
    #                 },
    #                 "end_time": {
    #                     "type": "array",
    #                     "items": {"type": "string"},
    #                 },
    #                 "is_paid": {
    #                     "type": "boolean",
    #                 },
    #                 "has_promotion": {
    #                     "type": "boolean",
    #                 },
    #                 "promotion_details": {
    #                     "type": "string",
    #                 },
    #                 "payment_mode": {
    #                     "type": "string",
    #                     "enum": [
    #                         "ticket",
    #                         "paid_membership",
    #                         "appointment",
    #                         "in_premises",
    #                     ],
    #                 },
    #                 "payment_details": {
    #                     "type": "string",
    #                 },
    #                 "links": {
    #                     "type": "array",
    #                     "items": {"type": "string"},
    #                 }
    #             },
    #             "required": ["name", "description", "categories"],
    #         },
    #     }], {"name": "create_event"}
