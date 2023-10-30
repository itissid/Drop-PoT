import json
import logging
from typing import Tuple

import requests
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class CodeAndMessage(BaseModel):
    code: int
    message: str


class ErrorResponse(BaseModel):
    error: CodeAndMessage


class Summary(BaseModel):
    distance: float
    duration: float


class Route(BaseModel):
    summary: Summary


class SuccessfulResponse(BaseModel):
    routes: list[Route]


def get_transit_distance_duration(
    lat1: float, lon1: float, lat2: float, lon2: float
):
    url = "http://127.0.0.1:8080/ors/v2/directions/{profile}"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
    }
    data = {"coordinates": [[lon1, lat1], [lon2, lat2]], "radiuses": [-1]}

    profiles = ["driving-car", "foot-walking"]
    directions = {}

    for profile in profiles:
        response = requests.post(
            url.format(profile=profile), headers=headers, json=data, timeout=3
        )
        if response.status_code == 200:
            try:
                response_data = SuccessfulResponse.model_validate_json(
                    response.text
                )
                directions[profile] = {
                    "distance": response_data.routes[0].summary.distance,
                    "duration": response_data.routes[0].summary.duration,
                    "units": {"distance": "meters", "duration": "seconds"},
                }
            except ValidationError as ex:
                logger.exception(
                    "Failed to parse successful response for profile %s: %s",
                    profile,
                    str(ex),
                )
                raise ex
        else:
            try:
                error_data = ErrorResponse.model_validate(response.json())
                directions[profile] = {
                    "error": {
                        "code": error_data.error.code,
                        "message": error_data.error.message,
                    }
                }
            except ValidationError as ex:
                logger.exception(
                    "Failed to parse error response for profile %s: %s",
                    profile,
                    str(ex),
                )
                raise ex

    return directions
