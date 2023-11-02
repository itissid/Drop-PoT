import enum
import logging
import math
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


class TransitDistanceDurationCalculator:
    def __init__(
        self,
        ors_api_endpoint="http://127.0.0.1:8080/ors/v2/directions/{profile}",
    ):
        # Incase of a time out connecting to ORS
        self.should_use_fallback_distance = False
        self.ors_api_endpoint = ors_api_endpoint
        self.default_walking_speed = (
            1.42  # Assume walking at 5 kmph. This is m/s
        )
        self.default_driving_speed = 11.16  # Assume driving at 40 kmph

    def _should_use_fallback_distance(
        self,
        direction: Dict[
            Profile, Union[TransitDirectionSummary, TransitDirectionError]
        ],
    ):
        # use haversine distance if the error in any one profile has a 999 time out error return true
        for _, val in direction.items():
            if isinstance(val, TransitDirectionError) and val.code == 999:
                return True
        return False

    def get_transit_distance_duration_wrapper(
        self, source_lat, source_lon, geo_dict: dict[str, GeoLocation]
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

        return_data = []

        for address, geoloc in geo_dict.items():
            val_or_error = self.get_transit_distance_duration(
                source_lat,
                source_lon,
                geoloc.latitude,
                geoloc.longitude,
                self.should_use_fallback_distance,
            )
            if self._should_use_fallback_distance(val_or_error):
                self.should_use_fallback_distance = True
                return_data.append(
                    (
                        self.get_transit_distance_duration(
                            source_lat,
                            source_lon,
                            geoloc.latitude,
                            geoloc.longitude,
                            self.should_use_fallback_distance,
                        ),
                        address,
                    )
                )
            else:
                return_data.append((val_or_error, address))
        return sorted(
            return_data,
            key=lambda x: _fn(*x),
        )

    @staticmethod
    def haversine_distance(coord1, coord2):
        # Radius of Earth in kilometers
        R = 6371.0

        # Convert latitude and longitude from degrees to radians
        lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
        lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])

        # Compute differences in latitude and longitude
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        # Haversine formula
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        # Distance in meters
        distance = R * c * 1000

        return distance

    def get_transit_distance_duration(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
        use_haversine=False,
    ) -> Dict[Profile, Union[TransitDirectionSummary, TransitDirectionError]]:
        if use_haversine:
            distance = self.haversine_distance((lat1, lon1), (lat2, lon2))
            walking_time = distance / self.default_walking_speed  # Assume walking at 5 kmph
            driving_time = distance / self.default_driving_speed  # Assume driving at 40 kmph
            return {
                Profile.foot_walking: TransitDirectionSummary(
                    distance,
                    walking_time,
                    Units("meters", "seconds"),
                ),
                Profile.driving_car: TransitDirectionSummary(
                    self.haversine_distance((lat1, lon1), (lat2, lon2)),
                    driving_time,
                    Units("meters", "seconds"),
                ),
            }
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
            try:
                response = requests.post(
                    self.ors_api_endpoint.format(profile=profile.value),
                    headers=headers,
                    json=data,
                    timeout=3,
                )
            except (
                requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError,
            ) as exc:
                logger.exception(
                    "Read or connection Timeout for profile %s", profile.value
                )
                directions[profile] = TransitDirectionError(999, str(exc))
                continue
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
