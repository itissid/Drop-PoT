import colorama
import typer
import json
import click
from typing import Any, Dict, List, Optional, Union, cast
from colorama import Fore
from typing import NewType

app = typer.Typer()


class CustomDict:
    def __init__(self, value: Dict[str, str]):
        self.value = value

    def __repr__(self):
        return f"<CustomDict: value={self.value}>"


class CustomDictParser(click.ParamType):
    name = "CustomDict"

    def convert(self, value, param, ctx):
        return CustomDict(dict(item.split("=") for item in value.split(",")))


def would_you_like_to_continue() -> bool:
    user_option = typer.prompt(
        "Would you like to use the continue or exit? (yes/exit)",
        default="exit",
    )
    while user_option.lower() not in ["yes", "exit"]:
        typer.echo("Invalid input. Please enter 'yes' or 'exit'.")
        user_option = typer.prompt(
            "Would you like to use the continue or exit? (yes/exit)",
        )
    if user_option.lower() == "yes":
        return True
    elif user_option.lower() == "exit":
        return False
    return False


@app.command()
def ask_user(
    txt: str = typer.Argument(..., help="Text to ask the user"),
    data_to_format: CustomDict = typer.Option(
        None,
        help="Data to format into the text",
        click_type=CustomDictParser(),
    ),
):
    ask_user_helper(txt, data_to_format.value if data_to_format else None)


def ask_user_helper(txt: str, data_to_format: Optional[Dict[str, str]] = None):
    if data_to_format:
        txt = txt.format(
            **{
                k: _optionally_format_colorama(
                    str(v), should_format=True, color=Fore.GREEN
                )
                for k, v in data_to_format.items()
            }
        )
    typer.echo(
        _optionally_format_colorama(
            txt, should_format=True, color=Fore.LIGHTBLUE_EX
        )
    )


# Generated via ChatGPT4 :) # Todo
def validate_url_file_suggestions(
    loaded_json: List[Dict[str, Union[str, Dict[str, str]]]],
    should_term_color: bool = False,
) -> Dict[str, str]:
    result = {}
    for item in loaded_json:
        url = item.get("url")
        file_names = item.get("file_names")
        if not url or not file_names or not isinstance(file_names, dict):
            raise ValueError("Bad data: missing URL or file names.")
        url = cast(str, url)
        typer.echo(
            f"\nURL: {_optionally_format_colorama(url, should_format=should_term_color, color=Fore.BLUE)}"
        )

        file_names = cast(Dict[str, str], file_names)

        default_option = file_names.get("a")
        if not default_option or not isinstance(default_option, str):
            raise ValueError("Bad data: Default file name cannot be empty!")

        typer.echo(
            f"Default file name: {_optionally_format_colorama(default_option, should_term_color, color=Fore.GREEN)}"
        )
        user_option = typer.prompt(
            "Would you like to use the default file name? (yes/no)",
            default="yes",
        )
        while user_option.lower() not in ["yes", "no"]:
            typer.echo("Invalid input. Please enter 'yes' or 'no'.")
            user_option = typer.prompt(
                "Would you like to use the default file name? (yes/no)"
            )

        if user_option.lower() != "yes":
            typer.echo(
                "Choose another option: a, b, c, or type 'd' to specify your own."
            )
            for key, value in file_names.items():
                typer.echo(f"{key}: {value}")
            typer.echo("d: Specify my own filename.")

            user_input = typer.prompt("Your choice")

            while user_input not in file_names and user_input != "d":
                typer.echo("Invalid input. Please enter 'a', 'b', 'c', or 'd'.")
                user_input = typer.prompt("Your choice")

            if user_input in file_names:
                chosen_file = file_names[user_input]
            else:
                if user_input == "d":
                    chosen_file = typer.prompt("Enter your custom file name")
                else:
                    chosen_file = user_input

            typer.echo(
                f"You've chosen: {_optionally_format_colorama(chosen_file, should_format=should_term_color,color=Fore.LIGHTGREEN_EX)}"
            )
            result[url] = chosen_file
        else:
            typer.echo(
                f"You've chosen the default file name: {_optionally_format_colorama(default_option, should_format=should_term_color, color=Fore.LIGHTGREEN_EX)}\n"
            )
            result[url] = default_option
    return result


def _optionally_format_colorama(
    text: str, should_format: bool = False, color=None
) -> str:
    if not should_format:
        return text
    else:
        if not color:
            raise ValueError(
                "Color must be specified if should_format is True."
            )
        return color + text + Fore.RESET


@app.command()
def choose_file(json_data: str) -> Dict[str, str]:
    try:
        data = json.loads(json_data)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid JSON data.") from e

    try:
        colorama.init()
        return validate_url_file_suggestions(data, should_term_color=True)
    finally:
        colorama.deinit()


if __name__ == "__main__":
    app()
