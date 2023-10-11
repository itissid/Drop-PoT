import datetime
import logging
from pathlib import Path
from typing import List, Tuple

import click
import tiktoken as tk
import typer
from colorama import Fore

from ..lib.ai import AltAI
from ..lib.db import DB
from ..model.ai_conv_types import MessageNode, Role
from ..utils.cli_utils import _optionally_format_colorama

logger = logging.getLogger(__name__)

app = typer.Typer()


@app.command()
def run_ai_with_user_cli_input(
    override_token_limit: int = typer.Option(
        4196,
        help="Override the default token limit for the algorithm to split the data to",
    ),
    file_prefix: str = typer.Option(
        "tmp_file", help="Prefix for the file name"
    ),
) -> None:
    datetime_filename = datetime.datetime.now().strftime(
        file_prefix + "_%Y%m%d_%H%M%S"
    )
    temp_dir = Path("/tmp/ai_adhoc/")
    logger.info(f"File will be in {temp_dir/datetime_filename}")

    typer.echo("Enter system prompt instructions to give to the GPT API")
    system_input = _get_multiline(marker="# Enter the system prompt below\n")
    print(system_input)
    assert system_input is not None
    typer.echo(
        "Please paste the data you want GPT API to process per the system prompt."
    )
    user_input = _get_multiline(marker="# Enter the user prompt below\n")
    assert user_input is not None
    # Break the user input into lines that are enough for tik to
    alt_ai = AltAI()
    messages = alt_ai.send(
        [
            MessageNode(content=system_input, role=Role.SYSTEM),
            MessageNode(
                content="I will shortly provide the user data in triple back ticks; wait for it and parse the data according to provided instructions",
                role=Role.USER,
            ),
        ]
    )
    try:
        parts = break_into_lines(
            ai.model, system_input, user_input, override_token_limit
        )
        print(f"Split into {len(parts)} parts")
        ai_separated_content = []
        for use_input_part in parts:
            messages = alt_ai.send(
                messages=messages[:1],
                prompt=f"Here is the data in triple back ticks; parse the data according to provided instructions\n```{use_input_part}```",
            )
            content = messages[-1]["content"]
            ai_separated_content.append(content)

        ingestion_db = DB(temp_dir)
        ingestion_db[datetime_filename] = "\n".join(ai_separated_content)
    except Exception as e:
        raise e


def _get_multiline(marker="# Everything below is ignored\n"):
    message = click.edit("\n\n" + marker)
    if message is not None:
        data = message.split(marker, 1)
        data = [i for i in data if i.strip()]
        return data[0].strip()


def break_into_lines(
    model: str, system_input: str, user_input: str, token_limit=4196
) -> List[str]:
    """
    Count the total tokens(using tiktoken) for model, system_input + user_input and then determine the line number where the
    user_input should be split so that the # of tokens < token_limit.
    Split and return the user_input into batches.
    """
    encoding = tk.encoding_for_model(model)
    total_tokens = len(
        encoding.encode(system_input) + encoding.encode(user_input)
    )
    if total_tokens < token_limit:
        typer.echo(f"Total tokens: {total_tokens} is within limits")
        return [user_input]
    else:
        # Determine the line number where number of token >= token_limit
        return _break_into_lines_internal(
            model,
            system_input,
            [(i, line) for i, line in enumerate(user_input.splitlines())],
            encoding,
            token_limit,
        )


def _break_into_lines_internal(
    model: str,
    system_input: str,
    user_input_lines: List[Tuple[int, str]],
    encoding,
    token_limit=4196,
    lookback: int = 10,
) -> List[str]:
    """
    We want to call AI by dividing the data into batches based on the token count.
    But before we do that we want to ask the user where in the range of line_number-K:line_number must
    that split be done adhering to token_limit. This method does that. For fairly large data this is useful.
    """
    typer.echo(f"Total lines in user input: {len(user_input_lines)}")
    total_till_now = len(encoding.encode(system_input))
    if not user_input_lines:
        return []
    limit_line_number = 0
    first_line_number = user_input_lines[0][0]
    limit_line_number = first_line_number
    total_tokens = len(
        encoding.encode(system_input)
        + encoding.encode("\n".join(line for _, line in user_input_lines))
    )
    if total_tokens < token_limit:
        typer.echo(f"Total tokens: {total_tokens} is withing limits")
        return ["\n".join("\n".join(line for _, line in user_input_lines))]

    for zero_offset_lno, (line_number, line) in enumerate(user_input_lines):
        limit_line_number = line_number
        total_till_now += len(encoding.encode(line))
        if total_till_now >= token_limit:
            break
    typer.echo(f"Total tokens: {total_till_now} till line number {line_number}")
    if limit_line_number <= first_line_number:
        raise ValueError(
            f"System+User input in the line is {total_till_now+len(encoding.encode(line))} (> Limit {token_limit})"
            + "Break it into multiple lines and try again."
        )

    # Using typer ask user where in the range of line_number-10:line_number must
    # the split be done.

    message = _message_lines_with_numbers(
        user_input_lines[max(0, zero_offset_lno - lookback) : zero_offset_lno]
    )
    NL = "\n"
    ln = "0"

    while (
        ln is not None
        and ln.isdigit()
        and not (
            limit_line_number - lookback <= int(ln) - 1 < limit_line_number
        )
    ):
        print()
        ln = typer.prompt(
            f"Choose the line number {_color('*before which*')} where the user input will be split:\n{message}"
        )

    print()
    typer.echo(
        f"Splitting till line number {ln} out of {len(user_input_lines)} lines"
    )
    data = ["\n".join(line for i, line in user_input_lines[: int(ln) - 1])]
    data.extend(
        _break_into_lines_internal(
            model,
            system_input,
            user_input_lines[int(ln) - 1 :],
            encoding,
            token_limit,
        )
    )
    return data


def _color(l):
    return _optionally_format_colorama(str(l), True, Fore.GREEN)


def _message_lines_with_numbers(lines: List[Tuple[int, str]]) -> str:
    return "\n".join([f"{_color(lno + 1)}: {line}" for lno, line in lines])


if __name__ == "__main__":
    app()
