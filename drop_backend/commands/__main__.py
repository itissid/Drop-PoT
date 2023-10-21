# Entry point for all commands. Set up things here like DB, logging or whatever.
import logging
from pathlib import Path
from typing import List

import click
import typer

from ..model.merge_base import bind_engine 
from ..lib.config_generator import check_should_update_schema
from ..lib.config_generator import gen_schema as gen_schema_impl
from ..lib.config_generator import generate_function_call_param_function
from ..utils.color_formatter import ColoredFormatter
from ..utils.db_utils import validate_database
from .mood_commands import generate_and_index_event_moods


app = typer.Typer()
data_ingestion_commands_app = typer.Typer(name="data-ingestion-commands")
config_generator_commands = typer.Typer(name="config-generator-commands")
LOG_FORMAT = "%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s"

logger = logging.getLogger(__name__)


@data_ingestion_commands_app.callback()
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

    if ctx.invoked_subcommand == "index-event-moods" or force_initialize_db:
        # pylint: disable=import-outside-toplevel,unused-import

        logger.info("Initializing database table")
        validate_database(test_db=test_db)
        bind_engine(obj["engine"])
        # combined_meta_data.create_all(bind=obj["engine"])


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
    batch_size: int = typer.Option(default=5, help="Batch size for messages(reduces cost)"),
):
    if not cities and not isinstance(cities, list):
        raise ValueError("Cities are required and must be a list.")
    if not demographics and not isinstance(demographics, list):
        raise ValueError("Demographics are required and must be a list.")
    demo_str = " and ".join(demographics)
    cities_str = " and ".join(cities)
    generate_and_index_event_moods(
        ctx, filename, version, cities_str, demo_str, batch_size  # Millenials and GenZ
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


app.add_typer(data_ingestion_commands_app)
app.add_typer(config_generator_commands)
data_ingestion_commands_app.command()(index_event_moods)
config_generator_commands.command()(gen_model_code_bindings)

if __name__ == "__main__":
    app()
