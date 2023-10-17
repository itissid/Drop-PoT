import importlib
import logging
from pathlib import Path
from types import ModuleType
from typing import Callable, Optional, Tuple

from colorama import Fore

from ..model.ai_conv_types import (
    EventNode,
    MessageNode,
    OpenAIFunctionCallSpec,
    UserExplicitFunctionCall,
)
from ..types.base import CreatorBase
from ..utils.cli_utils import _optionally_format_colorama, formatted_dict
from .config_generator import camel_to_snake

# The final cookie: Use this directly to get an EventNode If there is no
# function call protocol for the OpenAI api it does nothing an just creates the
# EventNode object.  If there is one it will set up hooks to callback and get
# the schema, the correct dataclass that was generated for `type_name`

logger = logging.getLogger(__name__)


class EventManager:
    def __init__(
        self,
        type_name: Optional[str] = None,
        type_module_prefix: Optional[str] = None,
        schema_module_prefix: Optional[str] = None,
    ):
        # TODO: make type_name be a list so one of many functions can be called.
        if not type_name:
            self._function_call_spec = lambda: (None, None)
            return
        schema_module = importlib.import_module(
            f"{schema_module_prefix}.{camel_to_snake(type_name)}_schema"
        )
        type_module_prefix = importlib.import_module(
            f"{type_module_prefix}.{camel_to_snake(type_name)}"
        )
        try:
            self._function_call_spec: Callable[
                [], Tuple[OpenAIFunctionCallSpec, UserExplicitFunctionCall]
            ] = getattr(
                schema_module,
                f"{camel_to_snake(type_name)}_function_call_param",
            )
        except AttributeError:
            raise Exception(
                f"Could not find function call spec for {type_name} in {schema_module_prefix}"
            )

        type_module_name = camel_to_snake(type_name)
        type_module = importlib.import_module(
            f"{type_module_prefix}.{type_module_name}"
        )
        try:
            self._event_obj_type: CreatorBase = getattr(type_module, type_name)
        except AttributeError:
            raise Exception(
                f"Could not find event object type for {type_name} in {type_module_name}"
            )

    def get_function_call_spec(
        self,
    ) -> Tuple[OpenAIFunctionCallSpec, UserExplicitFunctionCall]:
        # from code gen'ned module
        return self._function_call_spec()

    def create_event_node(self, raw_event_str: str) -> EventNode:
        self._event_node = EventNode._create(raw_event_str)
        return self._event_node

    # Allows for pass through, if no function call is returned by AI API returns (None, None)
    # Extend me to call a function based on text responsea if API does not support it(i.e. unlike OpenAI)
    def try_call_fn_and_set_event(
        self, ai_message: MessageNode
    ) -> Tuple[Optional[object], Optional[str]]:
        content = ai_message.message_content

        logger.debug(content)  # Typically empty if there is a function call.
        function_call = {}
        if ai_message.ai_function_call is not None:
            function_call = ai_message.ai_function_call.model_dump()
        else:
            logger.debug("No AI function calling requested")
        fn_name = function_call.get("name", None)
        fn_args = function_call.get("arguments", "{}")

        if not fn_name or not fn_args:
            return None, None

        logger.debug("AI Function called")
        # N2S: This step could be used to create training data for a future model to do this better.
        event_obj = self._event_obj_type.create(**fn_args)
        self._event_node._event_obj = event_obj
        logger.debug(
            _optionally_format_colorama("Parsed event:", True, Fore.RED)
        )
        logger.debug(
            "\n".join(
                [
                    f"{k}: {str(v)} ({type(v)})"
                    for k, v in formatted_dict((event_obj.model_dump())).items()
                ]
            )
        )
        # The object returned by the function must have a reasonable __str__ to be useful.
        kv = ", ".join(f"{k}={repr(v)}" for k, v in dict(event_obj).items())
        return event_obj, f"{fn_name}({kv})"
