
from main.lib.config_generator import validate_schema

@validate_schema
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
    