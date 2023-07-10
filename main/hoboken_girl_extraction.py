import datetime
import json
from dataclasses import asdict
from pathlib import Path
import re
from typing import Dict, Generator, List, Optional
from sqlalchemy import create_engine

from colorama import Fore
import typer
from utils.db import DB
from utils.ai import AI
from utils.scraping import get_documents
from utils.cli_utils import (
    ask_user_helper,
    choose_file,
    would_you_like_to_continue,
    go_autopilot,
    edit_dict,
    _optionally_format_colorama,
    formatted_dict,
)
from utils.prompt_utils import (
    base_prompt_hoboken_girl,
    hoboken_girl_event_function_param,
)
from model.types import Event, create_event
from model.persistence_model import (
    add_event,
    get_column_by_version_and_filename,
    get_num_events_by_version_and_filename,
    ParsedEventTable,
    Base,
)
import click
from sqlalchemy_utils import database_exists, create_database

# from .main import engine
import logging


app = typer.Typer()

# LOGGING #
logger = logging.getLogger(__name__)
# Create a file handler.
file_handler = logging.FileHandler("app.log")

# Create a console handler.
console_handler = logging.StreamHandler()

# Create a formatter and add it to the handlers.
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add the handlers to the logger.
logger.addHandler(file_handler)
logger.addHandler(console_handler)


@app.callback()
def logging_setup(
    ctx: typer.Context,
    loglevel: str = typer.Option("INFO", help="Set the log level"),
    force_initialize_db: bool = False,
):
    """
    Setup logging configuration.
    """
    # Set the log level of the logger according to the command line argument
    loglevel = loglevel.upper()
    if loglevel not in ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]:
        logger.error(f"Invalid log level: {loglevel}. Defaulting to INFO.")
        loglevel = "INFO"
    logger.setLevel(getattr(logging, loglevel))
    logger.debug(f"In callback {ctx.invoked_subcommand}")
    click.get_current_context().obj = {}

    obj = click.get_current_context().obj
    if (
        ctx.invoked_subcommand == "extract-serialize-events"
        or force_initialize_db
    ):
        logger.info("Initializing Drop database")
        obj["engine"] = create_engine("sqlite:///drop.db")
        if not database_exists(obj["engine"].url):  # Checks for the first time
            create_database(obj["engine"].url)  # Create new DB
            print(
                "New Database Created: "
                + str(database_exists(obj["engine"].url))
            )  # Verifies if database is there or not.
        else:
            print("Database Already Exists")
        Base.metadata.create_all(bind=obj["engine"])


# LOGGING #


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
    ai = AI()
    _ingest_urls_helper(urls, ingestion_db, ai)


def _ingest_urls_helper(
    urls: List[str],
    db: DB,
    ai: AI,
) -> dict[str, Path]:
    """Ingest a url and return the path to the scraped file."""

    # Ask AI to create 3 file name suggestions for this parsed file.
    def ask():
        now = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return ai.start(
            system=f"""
        I want you to suggest at least 3 *unique* file names for each of the URL I will provide.

        Here are the instructions: 
        1. Use the text in the URL information to create the file name leave out the HTTP(S) and www part.
        2. Never use special characters like: [!@#$%^&*()+{{}}|:"<>?] for a file name. Only use _ in the name.
        3. Add `{now}` suffix to each filename as well.
        4. The extension of the files is always .txt.
        5. Only output the json in the response and NO OTHER TEXT. 
        6. The file names for each URL *MUST BE UNIQUE* so add an additional suffix to them to make them unique.
        6. Generate the output in json array format following this template:
    
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
):
    """
    Call parse_events and get
    """

    if ingestable_article_file:
        ingestable_article_file = Path(ingestable_article_file).absolute()
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
        # TODO: Fetch failed events from database and retry them.
        pass
    if not events:
        logger.warn("No events found. Exiting")
        return

    # 1. Send System prompt.

    ai = AI()
    messages = ai.start(
        base_prompt_hoboken_girl(cities, date.strftime("%Y-%m-%d")),
        # NOTE: Add an optional clarification Step, here is where we might add a hook prompt for the AI to ask the user in case anything is unclear
        # this can be useful for AI to self reflect and produce more grounded prompts.
        "Wait for me to send/paste an event below.",
    )
    print(f"I have {len(messages)} messages in my memory and the last was:")
    # TODO: Add some assertion about messages recieved
    print(messages[-1]["content"])

    max_acceptable_errors = 5
    num_errors = 0

    element_names_already_seen = set(
        get_column_by_version_and_filename(
            ctx.obj["engine"],
            "name",
            version,
            ingestable_article_file.name,
        )
    )

    autopilot = False
    for i, event in enumerate(events):
        # 2. Send the remaining prompts
        try:
            event_obj = _parse_events(ai, messages[:1], event)
            if not event_obj:
                # TODO: Log this in SQL as an error in processing as NoEventFound.
                engine = ctx.obj["engine"]
                add_event(
                    engine,
                    event=None,
                    original_text=event,
                    failure_reason="NoEventFunctionCallByAI",
                    filename=ingestable_article_file.name,
                    version=version,
                )
                continue
            if not autopilot:
                typer.echo("Confirm is the event looks correct or edit it")
                typer.echo(
                    f"{_optionally_format_colorama('Raw Event text', True, Fore.GREEN)}'\n'{event}"
                )
                edit_dict(asdict(event_obj))
                # The user may want to turn on autopilot after a few events.
                if go_autopilot():
                    typer.echo(
                        "Autopilot is on. Processing all events without human intervention."
                    )
                    autopilot = True
            else:
                typer.echo(
                    f"Autopilot is on. Processing  event {_optionally_format_colorama(str(i+1), True, Fore.GREEN)} without human intervention."
                )
            engine = ctx.obj["engine"]
            if event_obj.name not in element_names_already_seen:
                add_event(
                    engine,
                    event=event_obj,
                    original_text=event,
                    failure_reason=None,
                    filename=ingestable_article_file.name,
                    version=version,
                )
            else:
                logger.debug(
                    f"Skipping {i}th event with name {event_obj.name} as it was already seen."
                )
        except Exception as e:
            engine = ctx.obj["engine"]
            id = add_event(
                engine,
                event=None,
                original_text=event,
                failure_reason=str(e),
                filename=ingestable_article_file.name,
                version=version,
            )
            logger.error(f"Error processing event {id}")
            logger.exception(e)
            if num_errors > max_acceptable_errors:
                typer.echo(
                    f"Too many errors. Stopping processing. Please fix the errors and run the command again."
                )
                return
            num_errors += 1
            continue
    logger.info(f"Done processing all events with {num_errors} errors.")


ALLOWED_FUNCTIONS = {
    "create_event": create_event,
}


def _event_gen(ingestable_article_file: Path):
    with open(ingestable_article_file, "r") as f:
        lines = f.readlines()
        all_text = "\n".join(lines)
        # split the text on the $$ delimiter using regex and strip leading and trailing newlines, whitespaces
        # TODO: Replace with a yield function
        events = [
            event.strip() for event in re.split(r"\n+\$\$\$\n+", all_text)
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


def _parse_events(
    ai: AI, base_messages: List[Dict[str, str]], event: str
) -> Optional[Event]:
    """
    This function will take the event text and parse it into an Event object using AI
    If event is not parsed we leave it to the caller to decide what to do with it.

    TODO: Replace hoboken_girl_event_function_param with a generic Callable.
    TODO: Write a test to mock out the AI and test various values for messages.
    """
    messages = ai.next(
        base_messages,
        f"""
            Process the following event in backticks according to the instructions provided previously.
            ```
            {event}
            ```
        """,
        function=hoboken_girl_event_function_param(),
        explicitly_call=True,
    )
    content = messages[-1]["content"]

    logger.debug(content)  # Typically empty if there is a function call.
    function_call = json.loads(messages[-1].get("function_call", "{}"))
    fn_name = function_call.get("name")
    fn_args = json.loads(function_call.get("arguments", "{}"))

    # NOTE: This step could be used to create training data for a future model to do this better.
    event_obj = None
    if fn_name and fn_name in ALLOWED_FUNCTIONS:
        event_obj = ALLOWED_FUNCTIONS[fn_name](**fn_args)
        logger.debug(
            f"{_optionally_format_colorama('Raw event:', True, Fore.RED)}\n{event}"
        )
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
    else:
        logger.warn(
            f"*** No function name found or not in Allowed functions list: {','.join(ALLOWED_FUNCTIONS.keys())}! for event: \n{event}"
        )
        logger.warn(f"Last message recieved from AI: {content}")
    return event_obj


def events_gen(filename: str, n_expected_events: int) -> Generator:
    # Write a function that accepts a filename and returns a generator that yields one event at a time.

    with open(filename, "r") as f:
        all_lines = f.readlines()
        data = "\n".join(all_lines)
        event_groups = data.split("\n\n$$\n\n")
        assert len(event_groups) == n_expected_events  # Safety check
        for event_string in event_groups:
            yield event_string


def _serialize_event(event: Event):
    pass


def system_prompt(db: DB):
    """
    TODO: Write a function that will use the file hoboken_girl_prompt.txt to generate a system prompt for the user.
    db: DB object that reads the file containing the prompt
    it will return a list of
    """
    functions = [
        {
            "name": "create_event",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                    },
                },
                "required": ["location"],
            },
        }
    ]


if __name__ == "__main__":
    app()
