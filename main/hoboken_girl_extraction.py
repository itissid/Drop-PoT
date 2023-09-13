import datetime
import json
import logging
import logging.config
import os
import re
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Dict, Generator, List, Optional, Tuple

import click
import typer
from colorama import Fore
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy_utils import create_database, database_exists

from main.commands.embedding_commands import demo_retrieval  # index_events,
from main.commands.embedding_commands import (index_event_embeddings,
                                              index_mood_embeddings,
                                              index_moods)
from main.hoboken_girl.function_call import hoboken_girl_event_function_param
from main.lib.ai import AIDriver, AltAI, driver_wrapper
from main.lib.db import DB
from main.lib.interrogation import InteractiveInterrogationProtocol
from main.model.ai_conv_types import (EventNode, InterrogationProtocol,
                                      MessageNode, Role)
from main.model.mood_model import Base as MoodBase
from main.model.persistence_model import Base as PersistenceBase
from main.model.persistence_model import (
    ParsedEventTable, add_event, get_column_by_version_and_filename,
    get_num_events_by_version_and_filename)
from main.model.types import Event, create_event
from main.utils.cli_utils import (_optionally_format_colorama, ask_user_helper,
                                  choose_file, formatted_dict,
                                  would_you_like_to_continue)
from main.utils.color_formatter import ColoredFormatter
from main.utils.prompt_utils import (base_prompt_hoboken_girl,
                                     default_parse_event_prompt)
from main.utils.scraping import get_documents

app = typer.Typer()

# LOGGING #
log_format = "%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# TODO(Sid): Move the invoke_subcommand checks to individual command files where it is used,
# we can oveeride @app.callback there.


@app.callback()
def setup(
    ctx: typer.Context,
    loglevel: str = typer.Option("INFO", help="Set the log level"),
    force_initialize_db: bool = False,
    test_db: bool = False
):
    """
    Setup logging configuration.
    """
    # Set the log level of the logger according to the command line argument
    loglevel = loglevel.upper()
    if loglevel not in ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]:
        logger.error(f"Invalid log level: {loglevel}. Defaulting to INFO.")
        loglevel = "INFO"
    print(f"loglevel: {loglevel}")
    root_logger = logging.getLogger()
    root_logger.setLevel(loglevel)
    colored_formatter = ColoredFormatter(log_format)
    for handler in root_logger.handlers:
        handler.setFormatter(colored_formatter)
    logger.debug(f"In callback {ctx.invoked_subcommand}")
    click.get_current_context().obj = {}

    obj = click.get_current_context().obj

    if (
        ctx.invoked_subcommand == "extract-serialize-events"
        or force_initialize_db
    ):
        logger.info("Initializing Drop database")
        _validate_database(test_db=test_db)
        PersistenceBase.metadata.create_all(bind=obj["engine"])
    elif (ctx.invoked_subcommand == "index-moods"):
        from model.mood_model import (MoodJsonTable,
                                      SubmoodBasedEmbeddingTextAccessorTable)
        _validate_database(test_db=test_db)
        MoodBase.metadata.create_all(bind=obj["engine"])
    elif ctx.invoked_subcommand == "index-events":
        from model.persistence_model import ParsedEventTable
        _validate_database(test_db=test_db)
        PersistenceBase.metadata.create_all(bind=obj["engine"])
    elif ctx.invoked_subcommand == "index-mood-embeddings":
        from model.mood_model import SubmoodBasedEmbeddingsTable
        _validate_database(test_db=test_db)
        MoodBase.metadata.create_all(bind=obj["engine"])
    elif ctx.invoked_subcommand == 'index-event-embeddings':
        from model.persistence_model import ParsedEventEmbeddingsTable
        _validate_database(test_db=test_db)
        PersistenceBase.metadata.create_all(bind=obj["engine"])
    elif force_initialize_db:
        logger.info("Force Initializing Drop database.")
        _validate_database(test_db=test_db)
        from model.persistence_model import (ParsedEventEmbeddingsTable,
                                             ParsedEventTable)
        PersistenceBase.metadata.create_all(bind=obj["engine"])
        from model.mood_model import (MoodJsonTable,
                                      SubmoodBasedEmbeddingsTable,
                                      SubmoodBasedEmbeddingTextAccessorTable)
        MoodBase.metadata.create_all(bind=obj["engine"])


def _validate_database(test_db: bool = False):
    obj = click.get_current_context().obj
    if test_db:
        url = "sqlite:///test_drop.db"
    else:
        url = "sqlite:///drop.db"
    print(f"Initalizing database at {url}")
    if not database_exists(url):  # Checks for the first time
        create_database(url)  # Create new DB
        print(
            "New Database Created: "
            + str(database_exists(obj.get("engine", url)))
        )  # Verifies if database is there or not.
    if not obj.get("engine"):
        obj["engine"] = create_engine(url)
    else:
        print("Engine already Exists")

# END LOGGING #


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
    ai = AltAI()
    _ingest_urls_helper(urls, ingestion_db, ai)


def _ingest_urls_helper(
    urls: List[str],
    db: DB,
    ai: AltAI,
) -> dict[str, str]:
    """Ingest a url and return the path to the scraped file."""

    # Ask AI to create 3 file name suggestions for this parsed file.
    def ask():
        now = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return ai.send(
            system=f"""
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
            user=f"Here are the URLS. I want you to suggest *3 unique* file names for each based on previous instructions: '\n'.join({urls})",
        )

    messages = ask()
    json_content = re.findall(
        r"`{0,3}(.*)`{0,3}", messages[-1]["content"], re.DOTALL
    )[0]
    url_file_names = choose_file(json_content)
    # Sanity check
    if len(url_file_names) != len(urls):
        raise ValueError(
            "Internal error: umber of URLs and file names don't match. Got {url_file_names}, for URLs {urls}"
        )
    # URLs may get formatted differently by the llm so we extract the documents after wards.
    documents = get_documents([url for url, _ in url_file_names.items()])
    typer.echo(
        f"{','.join([(str(len(document)) + ' chars extracted for url: '+url) for url, document in documents.items()])} documents"
    )
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
    pattern = r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), [a-zA-Z]+ \d+(?:st|nd|rd|th) \| \d+(?::\d+)?(?:AM|PM)(?: – \d+(?::\d+)?(?:AM|PM))?|Ongoing until [a-zA-Z]+ \d+(?:st|nd|rd|th)"
    new_line = "\n$$$\n\n"  # New line to be inserted
    lines_to_insert = 1  # Number of lines above the matched pattern

    # Read the file
    with open(file_path, "r") as file:
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
    with open(f"{file_path}_postprocessed", "w") as file:
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
        help="The date when the web events appeared online. Typically sometime in the week when the events happened",
    ),
    ingestable_article_file: Optional[Path] = typer.Option(
        None,
        help="The file with scraped data on events separated by the $$ delimiter. If no file then the user will input text events manually on the terminal.",
    ),
    version: str = typer.Option(
        "v1", help="The version of the event extractor to use"
    ),
    retry_only_errors: bool = False,
    # Large enough.
    max_acceptable_errors: int = int(1e7),
    is_test: bool = True,
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
        ctx.obj["engine"], version, ingestable_article_file.name
    )
    # A bit of sanity check.
    if items > 0:
        typer.echo(
            f"There are already {items} events in the database for the {version} version and file {ingestable_article_file.name}"
        )
        if not would_you_like_to_continue():
            return
        else:
            typer.echo("Duplicate events will be added to the database!")

    if not retry_only_errors:
        events = _event_gen(ingestable_article_file)
    else:
        # TODO: Fetch failed events from database and retry them. Maybe have somekind
        # of a queue abstraction that I can read failure events from instead of using
        # SQLLite as a "queue" for such things.
        pass
    if not events:
        logger.warn("No events found. Exiting")
        return

    ai = AltAI()
    ai_driver = AIDriver(ai)

    system_message = MessageNode(
        role=Role.system,
        message_content=base_prompt_hoboken_girl(
            cities, date.strftime("%Y-%m-%d")),
    )
    num_errors = 0
    driver_wrapper_gen = hoboken_girl_driver_wrapper(events, system_message, ai_driver,
                                                     interrogation_callback=InteractiveInterrogationProtocol())
    for event, error in driver_wrapper_gen:
        if error:
            assert isinstance(
                error, ValidationError), "Only validation error expected to be handled. You may want to add more error handling here."
            assert event.history is not None
            add_event(
                ctx.obj["engine"],
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
                ctx.obj["engine"],
                event=event.event_obj,
                original_text=event.raw_event_str,
                replay_history=event.history,
                failure_reason=None,
                filename=ingestable_article_file.name,
                version=version,
            )
        except Exception as e:
            engine = ctx.obj["engine"]
            id = add_event(
                engine,
                event=None,
                original_text=event.raw_event_str,
                replay_history=event.history,
                failure_reason=str(e),
                filename=ingestable_article_file.name,
                version=version,
            )
            logger.exception(e)
            logger.warn(f"Event id #{id} saved with its error")
            if num_errors > max_acceptable_errors:
                typer.echo(
                    f"Too many errors. Stopping processing. Please fix the errors and run the command again."
                )
                return
            num_errors += 1
            continue


def hoboken_girl_driver_wrapper(
        # TODO: This functions does not do much and is actually part of the intergration test case.
        # I need to remove this function and instead just test the driver_wrapper directly.
        events: List[str],
        system_message: MessageNode,
        ai_driver: AIDriver,
        message_content_callable=lambda event_node: default_parse_event_prompt(
            event=event_node.raw_event_str),
        function_call_spec_callable=hoboken_girl_event_function_param,
        function_callable_for_ai_function_call=lambda ai_message: call_ai_generated_function_for_event(
            ai_message),
        interrogation_callback: Optional[InterrogationProtocol] = None,

) -> Generator[Tuple[EventNode, Optional[ValidationError]], None, None]:

    driver_gen = driver_wrapper(
        events,
        system_message,
        ai_driver,
        message_content_callable,
        function_call_spec_callable,
        function_callable_for_ai_function_call,
        interrogation_callback,
    )
    for event, error in driver_gen:
        if isinstance(event, EventNode):
            assert event.history, "No conversational record found for event. Something is very wrong."
            yield event, error
        else:
            # NOTE(Ref1): this is where we would add the HIL bit.
            raise NotImplementedError("Only EventNode is supported for now.")


# This will become a *config* later.
ALLOWED_FUNCTIONS = {
    "create_event": create_event,
}


def call_ai_generated_function_for_event(ai_message: MessageNode) -> Tuple[Optional[Event], Optional[str]]:

    content = ai_message.message_content

    logger.debug(content)  # Typically empty if there is a function call.
    function_call = {}
    if ai_message.ai_function_call is not None:
        function_call = ai_message.ai_function_call.model_dump()
    fn_name = function_call.get("name", None)
    fn_args = function_call.get("arguments", "{}")

    # NOTE: This step could be used to create training data for a future model to do this better.
    event_obj = None
    if fn_name and fn_name in ALLOWED_FUNCTIONS:
        event_obj = ALLOWED_FUNCTIONS[fn_name](**fn_args)

        logger.debug(
            _optionally_format_colorama("Parsed event:", True, Fore.RED)
        )
        logger.debug(
            "\n".join(
                [
                    f"{k}: {str(v)} ({type(v)})"
                    for k, v in formatted_dict(asdict(event_obj)).items()
                ]
            )
        )
        # The object returned by the function must have a reasonable __str__ to be useful.
        return event_obj, f"{fn_name}({str(event_obj)})"
    else:
        logger.warn(
            f"*** No function name found or not in Allowed functions list: {','.join(ALLOWED_FUNCTIONS.keys())}! for event"
        )
        logger.warn(f"Last message recieved from AI: {content}")
    return None, None


def _event_gen(ingestable_article_file: Path):
    # NOTE: if we want to stream messages using the AIDriver, which is where the list of
    # events is used, we can make this a generator.
    with open(ingestable_article_file, "r") as f:
        lines = f.readlines()
        all_text = "\n".join(lines)
        # split the text on the $$ delimiter using regex and strip leading and trailing newlines, whitespaces
        # TODO: Replace with a yield function
        events = [
            event.strip() for event in re.split(r"\$\$\$", all_text)
        ]
        ask_user_helper(
            "There are {events} events in the file with an average of {avg} tokens per event.",
            data_to_format={
                "events": len(events),
                "avg": sum(len(event.split(" ")) for event in events)
                / (len(events) + 1),
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
