import logging
from dataclasses import asdict
from typing import Optional

import typer
from colorama import Fore

from main.model.ai_conv_types import (EventNode, InterrogationProtocol,
                                      MessageNode, Role)
from main.utils.cli_utils import (_optionally_format_colorama, formatted_dict,
                                  get_user_option)

logger = logging.getLogger(__name__)


class InteractiveInterrogationProtocol(InterrogationProtocol):
    """
    An interactive interrogation protocol that asks the user if they want to
    amend the response of the AI when it hs returned a function call result
    """

    def __init__(self) -> None:
        self._autopilot: bool = False
        self._interrogation: Optional[str] = None

    def get_interrogation_message(self, event: EventNode) -> Optional[MessageNode]:
        """ 
        # TODO: Add support for a function call for the user.

        get the last MessageNode from EventNode and if its role is assistant and it has a function call result
        then print the function call result and ask the user if they want to amend it
        """
        if not event.history:
            logger.warn("No event history found.")
            return None
        if self._autopilot:
            typer.echo(
                "Autopilot is on. Processing all events without human intervention."
            )
            return None
        last_message = event.history[-1]
        if last_message.role == Role.function and last_message.ai_function_call_result:
            print(
                f"AI function call result: {last_message.ai_function_call}")
            assert event.event_obj
            print(_optionally_format_colorama(
                "Parsed Event Object:", True, Fore.RED))
            print("\n".join(
                [
                    f"{k}: {str(v)} ({type(v)})"
                    for k, v in formatted_dict(dict(event.event_obj)).items()
                ]
            ))
            should_amend = self._ask_user_should_ai_amend()
            if should_amend:
                return MessageNode(
                    role=Role.user,
                    message_content=self._interrogation,
                    metadata={"is_interrogation": True},
                )
        return None

    def _ask_user_should_ai_amend(
            self,
            override_prompt: str = "Would you like to interact with Assistant to amend its response (yes/no/never)",
            choices=("yes", "no", "never"),
            default="never"
    ) -> bool:
        """
        Ask a user if they want to amend the response of the AI.
        """
        self._interrogation = None

        if self._autopilot:
            return False

        should_amend = get_user_option(
            override_prompt, choices, default)

        if should_amend == "never":
            self._autopilot = True
            return False

        if should_amend == "yes":
            while not self._interrogation:
                self._interrogation = typer.prompt(_optionally_format_colorama(
                    "Now, tell assistant what you want to fix: ", True, Fore.RED))
            return True

        return False
