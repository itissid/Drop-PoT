
import typing
from typing import List, Tuple

from main.model.ai_conv_types import OpenAIFunctionCallParameters
from main.model.ai_conv_types import OpenAIFunctionCallProperty as p
from main.model.ai_conv_types import (OpenAIFunctionCallSpec,
                                      UserExplicitFunctionCall)


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
                        items=p(
                            type="string"
                        ),
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
                        items=p(
                            type="string"
                        ),
                    )
                },
                required=["name", "description", "categories"],
            )
        )
    ]


def hoboken_girl_event_function_param() -> Tuple[List[OpenAIFunctionCallSpec], UserExplicitFunctionCall]:
    return hoboken_girl_event_function_param_spec(), UserExplicitFunctionCall(name="create_event")
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
