# Entry point for all commands. Set up things here like DB, logging or whatever.
import logging

import click
import typer

from ..lib.config_generator import gen_schema as gen_schema_impl
from ..model.merge_base import combined_meta_data
from ..utils.color_formatter import ColoredFormatter
from ..utils.db_utils import validate_database

# from . import mood_commands

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
        combined_meta_data.create_all(bind=obj["engine"])


def index_event_moods(ctx: typer.Context, filename: str, version: str):
    pass


#     mood_commands._generate_and_index_event_moods(ctx, filename, version)
from pathlib import Path


def gen_model_code_bindings(
    type_name: str,
    schema_directory_prefix: str = "main/types/schema",
    type_module_prefix: str = "main.types",
):
    schema_directory = Path(schema_directory_prefix)
    if (
        not schema_directory.exists()
        or not (schema_directory / "__init__.py").exists()
    ):
        typer.echo(f"Error: {schema_directory_prefix} is not a valid package!")
        raise typer.Exit(code=1)
    gen_schema_impl(type_name, schema_directory_prefix, type_module_prefix)


# app.add_typer(data_ingestion_commands_app)
app.add_typer(config_generator_commands)
data_ingestion_commands_app.command()(index_event_moods)
config_generator_commands.command()(gen_model_code_bindings)

if __name__ == "__main__":
    app()
