import json
import logging
import traceback
from typing import Dict, Optional, Tuple

import requests
import typer

from ..lib.ai import AltAI
from ..model.ai_conv_types import MessageNode, Role
from ..model.persistence_model import (
    ParsedEventTable,
    add_geoaddress,
    get_parsed_events,
)
from ..types.city_event import CityEvent

LOG_FORMAT = "%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s",
    handlers=[logging.StreamHandler()],
)


logger = logging.getLogger(__name__)


NOMINATIM_URL = "http://localhost:8080/search"


class HTTPException(Exception):
    def __init__(self, status_code, reason, content):
        self.status_code = status_code
        self.reason = reason
        self.content = content
        super().__init__(f"HTTP {status_code}: {reason}")


# N2S: If we use a public nominatim server, add waiting between requests
def get_coordinates(
    params: Dict[str, str]
) -> Tuple[Optional[float], Optional[float]]:
    # URL of your local Nominatim server

    # Make the API request
    response = requests.get(NOMINATIM_URL, params=params, timeout=5)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        data = json.loads(response.text)
        # Check if data was returned
        longitude, latitude = None, None
        if data:
            # Extract latitude and longitude from the first result
            # https://nominatim.org/release-docs/develop/api/Output/
            latitude = data[0]["lat"]
            longitude = data[0]["lon"]

        return latitude, longitude
    else:
        logger.error("Raised an error to nomatamin for Params %s ", str(params))
        raise HTTPException(
            response.status_code, response.reason, response.content
        )


def ask(address, alt_ai: AltAI) -> MessageNode:
    return alt_ai.send(  # pylint: disable=no-value-for-parameter
        [
            MessageNode(
                role=Role.system,
                message_content="""
            I am going to give you some addresses in a string format I want you to normalize them and return the normalized address in a json format.
        
            example if I give you : `1301 Hudson Street, Jersey City`. Return JSON in the following format(triple back ticks are important)):
            ```{
                "street": "1301 Hudson Street",
                "city": "Jersey City",
                "country": "United States",
            }``` 
            Use the following rules to do this:
            0. Do not add the State if its missing in the address.
            1. The addresses I provide you may be badly formatted or too general(since the data is from the web)
            in this case return NOTHING. Example If I give you `Jersey City` or `New York` only return nothing.
            2. Strip out what might be an apartment or suite number, state from the address. Like for example in:
            "1301 Adams Street C3, Hoboken"
            I want you to return the JSON:
            ```{
                "street": "1301 Adams Street",
                "city": "Hoboken",
                "country": "United States",
            }```
            stripping out the C3

            4. Return your answer in a **VALID** json delimited by triple back ticks. 

            Wait for me to paste the address.
        """,
            ),
            MessageNode(
                role=Role.user,
                message_content=(f"Here is the address: {address}"),
            ),
        ]
    )


def _try_format_address_with_ai(address: str) -> Optional[Dict[str, str]]:
    alt_ai = AltAI()
    ai_message = ask(address, alt_ai)
    address_str = (
        ai_message.message_content.replace("```", "")
        if ai_message.message_content
        else None
    )
    if address_str:
        try:
            address_json = json.loads(address_str)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Failed to parse json from `%s` due to %s", address_str, exc
            )
            raise exc
        return address_json
    else:
        logger.warning("Got no response from ai for %s", address)
    return None


def do_rcode(
    ctx: typer.Context,
    filename: str,
    version: str,
    parse_failed_only: bool = False,
) -> None:
    parsed_events = get_parsed_events(
        ctx,
        filename=filename,
        version=version,
        columns=[
            ParsedEventTable.id,
            ParsedEventTable.event_json,
            ParsedEventTable.name,
            ParsedEventTable.description,
        ],
        parse_failed_only=parse_failed_only,
    )
    typer.echo(f"Got {len(parsed_events)} events to process")
    for event in parsed_events:
        event_obj = CityEvent(
            **{
                **json.loads(event.event_json),
                **dict(name=event.name, description=event.description),
            }
        )
        addresses = event_obj.addresses
        if not addresses:
            logger.warning("No addresses found for event %d", event.id)
            continue
        for address in addresses:
            lat, long = None, None
            try:
                lat, long = get_coordinates(params={"q": address})
                if lat is None or long is None:
                    json_address = _try_format_address_with_ai(address)
                    if json_address:
                        lat, long = get_coordinates(json_address)
                    else:
                        raise ValueError(
                            f"Failed to get coordinates from AI as well for adddress {address}!"
                        )
            except Exception as exc:  #  pylint: disable=broad-exception-caught
                logger.warning(
                    "Failed to get coordinates for %s due to an error %s. Logging this as in the database for event id %d",
                    address,
                    exc,
                    event.id,
                )
                stack_trace = traceback.format_exc()
                add_geoaddress(
                    ctx,
                    parsed_event_id=event.id,
                    address=address,
                    failure_reason=str(stack_trace),
                )
                continue
            logger.debug("Adding address %s for id %d", address, event.id)
            add_geoaddress(
                ctx,
                parsed_event_id=event.id,
                address=address,
                latitude=lat,
                longitude=long,
                failure_reason=None
                if lat and long
                else "Failed to get find coordinates for this address",
            )


# N2S: Make sure your local Nominatim server is running and accessible at
# http://localhost:8080. Adjust the URL and port as needed.
