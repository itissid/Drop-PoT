import enum
import logging
from dataclasses import dataclass
from typing import Dict, Union

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


class Profile(str, enum.Enum):
    driving_car = "driving-car"
    foot_walking = "foot-walking"


@dataclass
class Units:
    distance: str
    duration: str


@dataclass
class TransitDirectionSummary:
    distance: float
    duration: float
    units: Units


@dataclass
class TransitDirectionError:
    code: int
    message: str


@dataclass
class GeoLocation:
    latitude: float
    longitude: float


def get_transit_distance_duration_wrapper(
    source_lat, source_lon, geo_dict: dict[str, GeoLocation]
):
    def _fn(
        direction: Dict[
            Profile, Union[TransitDirectionSummary, TransitDirectionError]
        ],
        _: str,
    ):
        if Profile.foot_walking in direction:
            foot_walking_dir = direction[Profile.foot_walking]
            if isinstance(foot_walking_dir, TransitDirectionError):
                return 1e12
            assert isinstance(foot_walking_dir, TransitDirectionSummary)
            return foot_walking_dir.duration
        return 1e12

    return sorted(
        [
            (
                get_transit_distance_duration(
                    source_lat, source_lon, geoloc.latitude, geoloc.longitude
                ),
                address,
            )
            for address, geoloc in geo_dict.items()
        ],
        key=lambda x: _fn(*x),
    )


def get_transit_distance_duration(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> Dict[Profile, Union[TransitDirectionSummary, TransitDirectionError]]:
    url = "http://127.0.0.1:8080/ors/v2/directions/{profile}"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
    }
    data = {"coordinates": [[lon1, lat1], [lon2, lat2]], "radiuses": [-1]}

    profiles = [
        Profile.driving_car,
        Profile.foot_walking,
    ]  # ["driving-car", "foot-walking"]
    directions: Dict[
        Profile, Union[TransitDirectionSummary, TransitDirectionError]
    ] = {}

    for profile in profiles:
        response = requests.post(
            url.format(profile=profile.value),
            headers=headers,
            json=data,
            timeout=3,
        )
        if response.status_code == 200:
            try:
                response_data = SuccessfulResponse.model_validate_json(
                    response.text
                )
                directions[profile] = TransitDirectionSummary(
                    response_data.routes[0].summary.distance,
                    response_data.routes[0].summary.duration,
                    Units("meters", "seconds"),
                )
            except ValidationError as ex:
                logger.exception(
                    "Failed to parse successful response for profile %s: %s",
                    profile.value,
                    str(ex),
                )
                raise ex
        else:
            try:
                error_data = ErrorResponse.model_validate(response.json())
                directions[profile] = TransitDirectionError(
                    error_data.error.code,
                    error_data.error.message,
                )
            except ValidationError as ex:
                logger.exception(
                    "Failed to parse error response for profile %s: %s",
                    profile,
                    str(ex),
                )
                raise ex

    return directions
