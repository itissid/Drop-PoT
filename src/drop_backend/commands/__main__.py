# Entry point for all commands. Set up things here like DB, logging or whatever.
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import click
import typer

from ..lib.config_generator import check_should_update_schema
from ..lib.config_generator import gen_schema as gen_schema_impl
from ..lib.config_generator import generate_function_call_param_function
from ..model.merge_base import bind_engine
from ..types.custom_types import When
from ..utils.color_formatter import ColoredFormatter
from ..utils.db_utils import validate_database
from ..utils.ors import Profile, TransitDirectionSummary
from .geo import do_rcode
from .mood_commands import generate_and_index_event_moods
from .webdemo_command_helper import geotag_moodtag_events_helper

app = typer.Typer()
config_generator_commands = typer.Typer(name="config-generator-commands")
LOG_FORMAT = "%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s"

logger = logging.getLogger(__name__)


def setup(
    ctx: typer.Context,
    loglevel: str = typer.Option("INFO", help="Set the log level"),
    force_initialize_db: bool = False,
    test_db: bool = False,
):
    loglevel = loglevel.upper()
    if loglevel not in ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]:
        logger.error("Invalid log level: %s. Defaulting to INFO.", loglevel)
        loglevel = "INFO"
    print(f"loglevel: {loglevel}")
    root_logger = logging.getLogger()
    root_logger.setLevel(loglevel)
    colored_formatter = ColoredFormatter(LOG_FORMAT)
    for handler in root_logger.handlers:
        handler.setFormatter(colored_formatter)
    logger.debug("In callback %s", ctx.invoked_subcommand)
    click.get_current_context().obj = {}
    obj = click.get_current_context().obj

    if (
        ctx.invoked_subcommand
        in set(["index-event-moods", "geotag-moodtag-events", "do-rcode"])
        or force_initialize_db
    ):
        # pylint: disable=import-outside-toplevel,unused-import

        logger.info("Initializing database table")
        validate_database(test_db=test_db)
        bind_engine(obj["engine"])


def index_event_moods(
    ctx: typer.Context,
    filename: str,
    version: str,
    cities: List[str] = typer.Option(
        help="A list of cities in which the events would be contextualized to"
    ),
    demographics: List[str] = typer.Option(
        help=(
            "A list of demographics in which the events would be contextualized"
            + "to examples could be like 'Millenials and GenZ'"
        )
    ),
    batch_size: int = typer.Option(
        default=5, help="Batch size for messages(reduces cost)"
    ),
):
    if not cities and not isinstance(cities, list):
        raise ValueError("Cities are required and must be a list.")
    if not demographics and not isinstance(demographics, list):
        raise ValueError("Demographics are required and must be a list.")
    demo_str = " and ".join(demographics)
    cities_str = " and ".join(cities)
    generate_and_index_event_moods(
        ctx,
        filename,
        version,
        cities_str,
        demo_str,
        batch_size,  # Millenials and GenZ
    )


def gen_model_code_bindings(
    type_name: str,
    schema_directory_prefix: str = "drop_backend/types/schema",
    type_module_prefix: str = "drop_backend.types",
):
    schema_directory = Path(schema_directory_prefix)
    if (
        not schema_directory.exists()
        or not (schema_directory / "__init__.py").exists()
    ):
        typer.echo(f"Error: {schema_directory_prefix} is not a valid package!")
        raise typer.Exit(code=1)
    # 0. Check if the generated schema already exists if it does ask user if they want to really replace it?
    update_schema = check_should_update_schema(
        type_name, schema_directory_prefix, type_module_prefix
    )
    # 1. generate the schema
    if not update_schema:
        typer.echo(f"Not updating/generating schema for {type_name}")
        return
    _, schema_module_prefix = gen_schema_impl(
        type_name, schema_directory_prefix, type_module_prefix
    )

    # 2. generate the function that uses schema
    schema_module = generate_function_call_param_function(
        type_name, schema_module_prefix, type_module_prefix
    )
    typer.echo(f"schema module is in path: {schema_module.__name__}")

    # Now use the event_node_manager.EventManager to use the schema as well as the type.


# Userful to test.
# # of events being returned is okay: Too low might mean,
# Events parsed by AI were bad.
# Reverse geotagging may have failed: rerun/fix it
# Mood tagging may have failed: rerun/fix it
# Some other bug in filtering data.
def geotag_moodtag_events(  # pylint: disable=too-many-arguments,too-many-locals
    ctx: typer.Context,
    filename: str,
    version: str,
    where_lat: float,
    where_lon: float,
    when: When = When.NOW,
    now_window_hours: int = 1,
    stubbed_now: Optional[datetime] = None,
):
    # stubbed_dict = {
    #     "hobokengirl_com_hoboken_jersey_city_events_november_10_2023_20231110_065435_postprocessed": [
    #         "v1",
    #         "v2",
    #     ],
    #     "hobokengirl_com_diwali_events_hudson_county_2023_20231110_065438_postprocessed": [
    #         "v1"
    #     ],
    # }
    datetime_now = stubbed_now or datetime.now()
    tagged_events = geotag_moodtag_events_helper(
        ctx.obj["engine"],
        "http://localhost:8080/ors/v2/directions/{profile}",
        {filename: [version]},
        # stubbed_dict,
        where_lat,
        where_lon,
        datetime_now,
        when,
        now_window_hours,
    )
    logger.info("Got %d tagged events", len(tagged_events))
    logger.info(
        "number of events with a Reverse GeoCoded lat long are %d",
        sum(1 for i in tagged_events if i.event.geo_dict),
    )

    def _direction(profile: Profile):
        logger.info(
            "Number of events with %s directions %d",
            profile,
            sum(
                1
                for te in tagged_events
                if te.directions
                and any(
                    direction_dict
                    and isinstance(
                        direction_dict.get(profile, None),
                        TransitDirectionSummary,
                    )
                    for direction_dict, _ in te.directions
                )
            ),
        )

    _direction(Profile.foot_walking)
    _direction(Profile.driving_car)


data_ingestion_commands_app = typer.Typer(
    name="data-ingestion-commands", callback=setup
)
app.add_typer(data_ingestion_commands_app)
app.add_typer(config_generator_commands)
reverse_geocoding_commands = typer.Typer(
    name="reverse-geocoding-commands", callback=setup
)
webdemo_adhoc_commands = typer.Typer(
    name="webdemo-adhoc-commands", callback=setup
)

app.add_typer(webdemo_adhoc_commands)
data_ingestion_commands_app.command()(index_event_moods)
config_generator_commands.command()(gen_model_code_bindings)
reverse_geocoding_commands.command()(do_rcode)
app.add_typer(reverse_geocoding_commands)

webdemo_adhoc_commands.command()(geotag_moodtag_events)

if __name__ == "__main__":
    app()
