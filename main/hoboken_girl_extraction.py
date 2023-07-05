import datetime
import json
from dataclasses import asdict
from pathlib import Path
import re
from typing import Generator, List, Optional

import click
import typer
from utils.db import DB
import enum
from utils.ai import AI
from utils.scraping import get_documents
from utils.cli_utils import (
    ask_user_helper,
    choose_file,
    would_you_like_to_continue,
)
from utils.prompt_utils import (
    base_prompt_hoboken_girl,
    hoboken_girl_event_function_param,
)
from model.types import Event, create_event


app = typer.Typer()


def events_gen(filename: str, n_expected_events: int) -> Generator:
    # Write a function that accepts a filename and returns a generator that yields one event at a time.

    with open(filename, "r") as f:
        all_lines = f.readlines()
        data = "\n".join(all_lines)
        event_groups = data.split("\n\n$$\n\n")
        assert len(event_groups) == n_expected_events  # Safety check
        for event_string in event_groups:
            yield event_string


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


# Custom post processing logic for hoboken girl files.
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
    for event in _parse_events(cities, date, ingestable_article_file):
        import ipdb
        ipdb.set_trace()
        print(event)


ALLOWED_FUNCTIONS = {
    "create_event": create_event,
}


def _parse_events(
    cities: List[str],
    date: datetime.datetime,
    ingestable_article_file: Path,
):
    # 1. Send System prompt.
    if not cities and type(cities) != list:
        raise ValueError("Cities are required and must be a list.")
    events = []
    # 1. Read the file and get the events.
    # 2. Ask the user if the number of events is correct.
    # 3. If not, ask the user to input the events manually.
    # 4. If yes, then parse the events.
    # 5. If parsing is not correct, ask the user to correct the fields.
    # 6. If parsing is correct, save the event.
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
            return

    typer.echo("Beginning parsing of events using AI.")
    ai = AI()
    messages = ai.start(
        base_prompt_hoboken_girl(cities, date.strftime("%Y-%m-%d")),
        # NOTE: Add an optional clarification Step, here is where we might add a hook prompt for the AI to ask the user in case anything is unclear
        # this can be useful for AI to self reflect and produce more grounded prompts.
        "Wait for me to paste an event below.",
    )
    for event in events:
        # print(event)

        messages = ai.next(
            messages[:1],
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
        print(content)
        function_call = json.loads(messages[-1]["function_call"])
        fn_name = function_call["name"]
        fn_args = asdict(function_call["arguments"])
        
        # TODO: Ask user if they want to continue in auto mode and save all the elements.
        # NOTE: What might be interesting is that this step could be used to create training data for a future model to do this better.
        event_obj = None
        if fn_name and fn_name in ALLOWED_FUNCTIONS:
            event_obj = ALLOWED_FUNCTIONS[fn_name](**fn_args)

            
        else:
            typer.echo(
                f"*** No function name found or not in Allowed functions list: {','.join(ALLOWED_FUNCTIONS.keys())}! for event: \n{event}"
            )
        yield event_obj
    # ai.start()
    # 2. User input: Ask the user: # Of events in the file is ok and process automatically.
    # 3. Assistant: Take event `i` and ask the user to confirm if the parsing was ok for all fields.
    # If not the user will specify the field's value to be corrected.
    # Those fields will be finally added to the event and it will be saved.
    # If the user says the event is ok, then save event as such.



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


# TODO:
#
# write an entry point with the cleaned pages from the HG and its published date, time zone, zip code and a prefix to use for
# logs written to the file system to a directory.
# TODO:
# Entry point that will scrape the pages for HG and return.

if __name__ == "__main__":
    app()
