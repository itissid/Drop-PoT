from prompts.hoboken_girl_prompt import HOBOKEN_GIRL_SYSTEM_PROMPT


def base_prompt_hoboken_girl(cities, date):
    return HOBOKEN_GIRL_SYSTEM_PROMPT.format(PLACES=cities, DATE=date)


def hoboken_girl_event_function_param():
    return {
            "name": "create_event",
            "description": "Parse an event's fields from the provided text",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                    },
                    "description": {
                        "type": "string",
                    },
                    "categories": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "string"}},
                    },
                    "addresses": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "string"}},
                    },
                    "is_ongoing": {
                        "type": "boolean",
                    },
                    "start_date": {
                        "type": "string",
                    },
                    "end_date": {
                        "type": "string",
                    },
                    "start_time": {
                        "type": "string",
                    },
                    "end_time": {
                        "type": "string",
                    },
                    "is_paid": {
                        "type": "boolean",
                    },
                    "has_promotion": {
                        "type": "boolean",
                    },
                    "promotion_details": {
                        "type": "string",
                    },
                    "payment_mode": {
                        "type": "string",
                        "enum": [
                            "ticket",
                            "paid_membership",
                            "appointment",
                            "in_premises",
                        ],
                    },
                    "payment_details": {
                        "type": "string",
                    },
                },
                "required": ["name", "description", "categories"],
            },
        }
