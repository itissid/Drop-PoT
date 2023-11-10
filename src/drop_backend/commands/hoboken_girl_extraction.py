import datetime
import logging
import logging.config
import re
from pathlib import Path
from typing import Generator, List, Optional, Tuple

import click
import typer
from pydantic import ValidationError

from ..commands.embedding_commands import demo_retrieval  # index_events,
from ..commands.embedding_commands import (
    index_event_embeddings,
    index_mood_embeddings,
    index_moods,
)
from ..lib.ai import AIDriver, AltAI, driver_wrapper
from ..lib.db import DB
from ..lib.event_node_manager import EventManager
from ..lib.interrogation import InteractiveInterrogationProtocol
from ..model.ai_conv_types import (
    EventNode,
    InterrogationProtocol,
    MessageNode,
    Role,
)
from ..model.merge_base import bind_engine
from ..model.persistence_model import (
    add_event,
    get_num_events_by_version_and_filename,
)
from ..prompts.hoboken_girl_prompt import (
    base_prompt_hoboken_girl,
    default_parse_event_prompt,
)
from ..utils.cli_utils import (
    ask_user_helper,
    choose_file,
    would_you_like_to_continue,
)
from ..utils.color_formatter import ColoredFormatter
from ..utils.db_utils import validate_database
from ..utils.scraping import get_documents

app = typer.Typer()

# LOGGING #
LOG_FORMAT = "%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

# TODO(Sid): Move the invoke_subcommand checks to individual command files where it is used,
# we can oveeride @app.callback there.


@app.callback()
def setup(
    ctx: typer.Context,
    loglevel: str = typer.Option("INFO", help="Set the log level"),
    test_db: bool = False,
):
    """
    Setup logging configuration.
    """
    # Set the log level of the logger according to the command line argument
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

    validate_database(test_db=test_db)
    bind_engine(obj["engine"])


@app.command()
def ingest_urls(
    injestion_path: str = typer.Argument("", help="path"),
    urls: List[str] = typer.Argument(..., help="urls to scrape"),
    run_prefix: str = typer.Option(
        ..., help="prefix to use for the directory name"
    ),
):
    input_path = Path(injestion_path).absolute()
    if not input_path.exists():
        typer.echo(f"Path {input_path} does not exist")
        raise typer.Exit(code=1)
    input_path = input_path / f"{run_prefix}_ingestion"
    ingestion_db = DB(input_path)
    alt_ai = AltAI()
    _ingest_urls_helper(urls, ingestion_db, alt_ai)


def _ingest_urls_helper(
    urls: List[str],
    db: DB,
    alt_ai: AltAI,
) -> dict[str, str]:
    """Ingest a url and return the path to the scraped file."""

    # Ask AI to create 3 file name suggestions for this parsed file.
    def ask() -> MessageNode:
        now = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return alt_ai.send(
            [
                MessageNode(
                    role=Role.system,
                    message_content=f"""
        I want you to suggest at least 3 *unique* file names for each of the URL I will provide.

        Here are the instructions: 
        1. Use the text in the URL information to create the file name. Leave out the HTTP(S) and www part of the file name.
        2. Never use special characters like: [!@#$%^&*()+{{}}|:"<>?] for a file name. Only use _ in the name.
        3. Add `{now}` suffix to each filename as well.
        4. The extension of the files is always .txt.
        5. Only output the json in the response and NO OTHER TEXT. 
        6. The file names for each URL *MUST BE UNIQUE* so add an additional suffix to them to make them unique. 
        7. Generate the output in json array format in triple backticks below.
        8. Make sure the URL keys in the JSON format are *exactly the same* as I provide. DO NOT CHANGE THEM.
    
        ```
        [{{
            "url": <url>, 
            "file_names": {{
                "a": <file_name_1>
                "b": <file_name_2>
                "c": <file_name_3>
            }}
        }}]
        ```
        """,
                ),
                MessageNode(
                    role=Role.user,
                    message_content=(
                        "Here are the URLS. I want you to suggest"
                        + "*3 unique* file names for each based on previous"
                        + f"instructions: '\n'.join({urls})"
                    ),
                ),
            ]
        )

    message = ask()
    assert message.message_content is not None
    json_content = message.message_content.lstrip("`").rstrip("`")
    url_file_names = choose_file(json_content)
    # Sanity check
    if len(url_file_names) != len(urls):
        raise ValueError(
            "Internal error: umber of URLs and file names don't match. Got"
            f"{url_file_names}, for URLs {urls}"
        )
    # URLs may get formatted differently by the llm so we extract the documents after wards.
    documents = get_documents([url for url, _ in url_file_names.items()])
    document_lengths = [
        f"{len(document)} chars extracted for url: {url}"
        for url, document in documents.items()
    ]
    result = f"{','.join(document_lengths)} documents"
    typer.echo(result)
    # Save the documents!
    for url, file_name in url_file_names.items():
        db[file_name] = documents[url]
    return url_file_names


# Custom post processing logic for hoboken girl files. Insert markers between events.
# Regex is imperfect but since the files have 1000+ events ... it's good enough for people to correct a few by hand.
@app.command()
def post_process(file_path: Path = typer.Argument()) -> None:
    input_path = Path(file_path).absolute()
    _post_process(file_path=input_path)


def _post_process(file_path: Path) -> None:
    # pylint
    pattern = r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), [a-zA-Z]+ \d+(?:st|nd|rd|th) \| \d+(?::\d+)?(?:AM|PM)(?: – \d+(?::\d+)?(?:AM|PM))?|Ongoing until [a-zA-Z]+ \d+(?:st|nd|rd|th)"
    new_line = "\n$$$\n\n"  # New line to be inserted
    lines_to_insert = 1  # Number of lines above the matched pattern

    # Read the file
    with open(file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    # Find and insert new lines
    matches = []
    for i, line in enumerate(lines):
        if re.search(pattern, line):
            matches.append(i)

    for match in reversed(matches):
        insert_index = max(0, match - lines_to_insert)
        lines.insert(insert_index, new_line)

    # Write the updated file
    with open(f"{file_path}_postprocessed", "w", encoding="utf-8") as file:
        file.writelines(lines)


@app.command()
def extract_serialize_events(
    ctx: typer.Context,
    cities: List[str] = typer.Option(
        help="A list of cities in which the events would be contextualized to"
    ),
    date: datetime.datetime = typer.Argument(
        ...,
        formats=["%Y-%m-%d"],
        help=(
            "The date when the web events appeared online. Typically sometime in the"
            "week when the events happened"
        ),
    ),
    ingestable_article_file: Optional[Path] = typer.Option(
        None,
        help=(
            "The file with scraped data on events separated by the $$ delimiter. "
            "If no file then the user will input text events manually on the terminal."
        ),
    ),
    version: str = typer.Option(
        "v1", help="The version of the event extractor to use"
    ),
    retry_only_errors: bool = False,
    skip_indexed_events: bool = False,
    # Large enough.
    max_acceptable_errors: int = int(1e7),
):
    """
    Call AI to parse all teh events in ingestable_article_file to extract
    structured events and then save them to the database as JSON.
    """

    if ingestable_article_file:
        ingestable_article_file = Path(ingestable_article_file).absolute()
        assert ingestable_article_file.exists()
    else:
        # TODO: Implement manual input to debug.
        typer.echo("No file not supported yet. Exiting")
        return
    if not cities and type(cities) != list:
        raise ValueError("Cities are required and must be a list.")
    items = get_num_events_by_version_and_filename(
        ctx, version, ingestable_article_file.name
    )
    if not retry_only_errors:
        events = _event_gen(ingestable_article_file)
    else:
        logger.warning("Retry logic not implemented yet. Bailing out")
        return
        # TODO: Fetch failed events from database and retry them. Maybe have somekind
        # of a queue abstraction that I can read failure events from instead of using
        # SQLLite as a "queue" for such things.
    # A bit of sanity check.
    if items > 0:
        typer.echo(
            (
                f"There are already {items} events in the database for"
                f" the {version} version and file {ingestable_article_file.name}"
            )
        )
        if skip_indexed_events:
            typer.echo("Flag set. Already indexing events will be skipped.")
            events = events[items:]
            typer.echo(f"There are {len(events)} events left to index")
        else: 
            typer.echo("Duplicate events will be added to the database!")
        if not would_you_like_to_continue():
            return

    if not events:
        logger.warning("No events found. Exiting")
        return

    ai = AltAI()  # pylint: disable=invalid-name
    event_manager = EventManager(
        "CityEvent", "drop_backend.types", "drop_backend.types.schema"
    )
    ai_driver = AIDriver(ai, event_manager=event_manager)

    system_message = MessageNode(
        role=Role.system,
        message_content=base_prompt_hoboken_girl(
            cities, date.strftime("%Y-%m-%d")
        ),
    )
    num_errors = 0
    driver_wrapper_gen = hoboken_girl_driver_wrapper(
        events,
        system_message,
        ai_driver,
        event_manager,
        interrogation_protocol=InteractiveInterrogationProtocol(),
    )
    for i, (event, error) in enumerate(driver_wrapper_gen):
        if error:
            assert isinstance(error, ValidationError), (
                "Only validation error expected to be handled. You may want to add more "
                "error handling here."
            )
            assert event.history is not None
            add_event(
                ctx,
                event=None,
                original_text=event.raw_event_str,
                replay_history=event.history,
                failure_reason=error.json(),
                filename=ingestable_article_file.name,
                version=version,
            )
            continue
        try:
            assert event.history is not None
            add_event(
                ctx,
                event=event.event_obj,
                original_text=event.raw_event_str,
                replay_history=event.history,
                failure_reason=None,
                filename=ingestable_article_file.name,
                version=version,
            )
        except Exception as error:  # pylint: disable=broad-except
            _id = add_event(  # pylint: disable=invalid-name
                ctx,
                event=None,
                original_text=event.raw_event_str,
                replay_history=event.history,
                failure_reason=str(error),
                filename=ingestable_article_file.name,
                version=version,
            )
            logger.exception(error)
            logger.warning("Event id #%d saved with its error", _id)
            if num_errors > max_acceptable_errors:
                logger.error(
                    (
                        "Too many errors. Stopping processing."
                        " Please fix the errors and run the command again."
                    )
                )
                return
            num_errors += 1
        finally:
            logger.info("Processed event %d", i)


def hoboken_girl_driver_wrapper(
    # TODO: This functions does not do much and is actually part of the intergration test case.
    # I need to remove this function and instead just test the driver_wrapper directly.
    events: List[str],
    system_message: MessageNode,
    ai_driver: AIDriver,
    event_manager: EventManager,
    interrogation_protocol: Optional[InterrogationProtocol] = None,
) -> Generator[Tuple[EventNode, Optional[ValidationError]], None, None]:
    driver_gen = driver_wrapper(
        events,
        system_message,
        ai_driver,
        user_message_prompt_fn=lambda event_node: default_parse_event_prompt(
            event=event_node.raw_event_str
        ),
        event_manager=event_manager,
        interrogation_protocol=interrogation_protocol,
    )
    for event, error in driver_gen:
        if isinstance(event, EventNode):
            assert (
                event.history
            ), "No conversational record found for event. Something is very wrong."
            yield event, error
        else:
            raise NotImplementedError("Only EventNode is supported for now.")


def _event_gen(ingestable_article_file: Path):
    # NOTE: if we want to stream messages using the AIDriver, which is where the list of
    # events is used, we can make this a generator.
    with open(ingestable_article_file, "r", encoding="utf-8") as file:
        lines = file.readlines()
        all_text = "\n".join(lines)
        # split the text on the $$ delimiter using regex and strip leading and
        # trailing newlines, whitespaces
        # Note: Consider Replace with a yield function
        events = [event.strip() for event in re.split(r"\$\$\$", all_text)]
        ask_user_helper(
            "There are {num_events} events in the file with an average of {avg} tokens per event.",
            data_to_format={
                "num_events": str(len(events)),
                "avg": str(
                    sum(len(event.split(" ")) for event in events)
                    / (len(events) + 1)
                ),
            },
        )
        # Ask if user if all is good before proceeding.
        if not would_you_like_to_continue():
            return None
    return events


app.command()(index_moods)
app.command()(index_mood_embeddings)
app.command()(index_event_embeddings)
app.command()(demo_retrieval)

if __name__ == "__main__":
    app()
