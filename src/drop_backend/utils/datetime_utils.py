from datetime import datetime
from typing import List


def assert_datetime_format(date_string, datetime_format: str) -> bool:
    try:
        datetime.strptime(date_string, datetime_format)
        return True
    except ValueError:
        return False


# TODO: Use in pydantic validation in the CityEvents class
def datetime_string_processor(
    datetime_string, accepted_time_formats: List[str], target_format: str
) -> str:
    for time_format in accepted_time_formats:
        if assert_datetime_format(datetime_string, time_format):
            return datetime.strptime(datetime_string, time_format).strftime(
                target_format
            )
    raise ValueError(
        "No valid time format found for time string: " + datetime_string
    )
