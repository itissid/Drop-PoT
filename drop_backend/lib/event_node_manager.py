import importlib
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional, Tuple

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

logger = logging.getLogger(__name__)


class BaseEventManager(ABC):
    """
    We can create any kind of function call 
    """
    def create_event_node(self, raw_event_str: str) -> EventNode:
        self._event_node = EventNode._create(raw_event_str)
        return self._event_node

    @abstractmethod
    def get_function_call_spec(
        self,
    ) -> Tuple[List[OpenAIFunctionCallSpec], UserExplicitFunctionCall]:
        ...

    @abstractmethod
    def extract_fn_name(self, ai_message: MessageNode) -> Optional[str]:
        ...

    @abstractmethod
    def extract_fn_args(
        self, ai_message: MessageNode
    ) -> (List[Any], Dict[str, Any]):
        ...

    @abstractmethod
    def should_call_function(self, ai_message: MessageNode) -> bool:
        ...

    @abstractmethod
    def call_fn_by_name(self, fn_name: str, *args, **kwargs):
        ...

    def try_call_fn_and_set_event(
        self, ai_message: MessageNode
    ) -> Tuple[Optional[object], Optional[str]]:
        """
        return an object created from calling a function based on content of ai_message.
        and the string representation of the API call :`fn_name(arg1=..., arg2=...)`

        Allows one to call any API based on AI response.
        """
        fn_name = self.extract_fn_name(ai_message=ai_message)
        fn_args, fn_kwargs = self.extract_fn_args(ai_message=ai_message)
        should_call_fn = self.should_call_function(ai_message=ai_message)
        if should_call_fn:
            return self.call_fn_by_name(fn_name=fn_name, *fn_args, **fn_kwargs)
        return None, None


class EventManager(BaseEventManager):
    """
    OpenAI specfic event manager. Reads our codegenned JSON Schema and creates
    the appropriate objects for API call; calls functions by name in our defined
    pydantic objects per types.base.CreatorBase.
    """

    def __init__(
        self,
        type_name: Optional[str] = None,
        type_module_prefix: Optional[str] = None,
        schema_module_prefix: Optional[str] = None,
    ):
        # TODO: make type_name be a list so one of many functions can be called.
        self.no_function_spec: bool = False
        if not type_name:
            self._function_call_spec = lambda: (None, None)
            self.no_function_spec = True
            return
        schema_module = importlib.import_module(
            f"{schema_module_prefix}.{camel_to_snake(type_name)}_schema"
        )

        try:
            self._function_call_spec: Callable[
                [],
                Tuple[List[OpenAIFunctionCallSpec], UserExplicitFunctionCall],
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
    ) -> Tuple[List[OpenAIFunctionCallSpec], UserExplicitFunctionCall]:
        # from code gen'ned module
        return self._function_call_spec()

    def extract_fn_name(self, ai_message: MessageNode) -> Optional[str]:
        if ai_message.ai_function_call is None:
            return None
        return ai_message.ai_function_call.name

    def extract_fn_args(
        self, ai_message: MessageNode
    ) -> (List[Any], Dict[str, Any]):
        if ai_message.ai_function_call is None:
            return [], {}
        return [], ai_message.ai_function_call.arguments

    def should_call_function(self, ai_message: MessageNode) -> bool:
        fn_name = self.extract_fn_name(ai_message=ai_message)
        if fn_name:
            return True
        else:
            logger.debug("No AI function calling requested")
            return False

    def call_fn_by_name(self, fn_name: str, *args, **kwargs) -> Tuple[Any, str]:
        event_obj = self._event_obj_type.create(function_name=fn_name, **kwargs)

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

    # # Allows for pass through, if no function call is returned by AI API returns (None, None)
    # # One can extend it to call a function based on text responses if API does not support it(i.e. unlike OpenAI):
    # # 1. extract the text from ai_message.message_content instead of ai_message.ai_function_call
    # # 2. Use self._event_obj_type.create or any bespoke function.
    # def try_call_fn_and_set_event(
    #     self, ai_message: MessageNode
    # ) -> Tuple[Optional[object], Optional[str]]:
    #     if self.no_function_spec:
    #         return None, None
    #     content = ai_message.message_content

    #     logger.debug(content)  # Typically empty if there is a function call.
    #     function_call = {}
    #     if ai_message.ai_function_call is not None:
    #         function_call = ai_message.ai_function_call.model_dump()
    #     else:
    #         logger.debug("No AI function calling requested")
    #     fn_name = function_call.get("name", None)
    #     fn_args = function_call.get("arguments", "{}")
    #     # N2S: if the API does not support function calls, we can use the text to call a function
    #     # and ignore the condition below where we override it.
    #     if not fn_name or not fn_args:
    #         logger.warning(
    #             "No function call found in ai response even though there was functon spec "
    #         )
    #         return None, None

    #     logger.debug("AI Function called")
    #     # N2S: This step could be used to hook in training data creation for a future model to do this better.
    #     event_obj = self._event_obj_type.create(
    #         function_name=fn_name, **fn_args
    #     )
    #     self._event_node._event_obj = event_obj
    #     logger.debug(
    #         _optionally_format_colorama("Parsed event:", True, Fore.RED)
    #     )
    #     logger.debug(
    #         "\n".join(
    #             [
    #                 f"{k}: {str(v)} ({type(v)})"
    #                 for k, v in formatted_dict((event_obj.model_dump())).items()
    #             ]
    #         )
    #     )
    #     # The object returned by the function must have a reasonable __str__ to be useful.
    #     kv = ", ".join(f"{k}={repr(v)}" for k, v in dict(event_obj).items())
    #     return event_obj, f"{fn_name}({kv})"
