import importlib
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast

from colorama import Fore  # type: ignore
from pydantic import BaseModel  # type: ignore

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
    We can create any kind of function call by overloading the below abstract methods.
    """

    def create_event_node(self, raw_event_str: str) -> EventNode:
        self._event_node = EventNode._create(  # pylint: disable=protected-access,attribute-defined-outside-init
            raw_event_str
        )
        return self._event_node

    @abstractmethod
    def get_function_call_spec(
        self,
    ) -> Tuple[
        Optional[List[OpenAIFunctionCallSpec]],
        Optional[UserExplicitFunctionCall],
    ]:
        ...

    @abstractmethod
    def extract_fn_name(self, ai_message: MessageNode) -> Optional[str]:
        ...

    @abstractmethod
    def extract_fn_args(
        self, ai_message: MessageNode
    ) -> Tuple[List[Any], Dict[str, Any]]:
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
            assert fn_name is not None
            return self.call_fn_by_name(fn_name, *fn_args, **fn_kwargs)
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
            logger.warning(
                "No type name provided. Not generating function call spec."
            )
            self._function_call_spec: Callable[
                [],
                Tuple[List[OpenAIFunctionCallSpec], UserExplicitFunctionCall],
            ] = lambda: (  # type: ignore
                None,
                None,
            )
            self.no_function_spec = True
            return
        schema_module = importlib.import_module(
            f"{schema_module_prefix}.{camel_to_snake(type_name)}_schema"
        )

        try:
            self._function_call_spec: Callable[  # type: ignore
                [],
                Tuple[List[OpenAIFunctionCallSpec], UserExplicitFunctionCall],
            ] = getattr(
                schema_module,
                f"{camel_to_snake(type_name)}_function_call_param",
            )
        except AttributeError as exc:
            raise ValueError(
                f"Could not find function call spec for {type_name} in {schema_module_prefix}"
            ) from exc

        type_module_name = camel_to_snake(type_name)
        type_module = importlib.import_module(
            f"{type_module_prefix}.{type_module_name}"
        )
        try:
            self._event_obj_type: Union[CreatorBase, BaseModel] = getattr(
                type_module, type_name
            )
        except AttributeError as exc:
            raise ValueError(
                f"Could not find event object type for {type_name} in {type_module_name}"
            ) from exc

    def get_function_call_spec(
        self,
    ) -> Tuple[
        Optional[List[OpenAIFunctionCallSpec]],
        Optional[UserExplicitFunctionCall],
    ]:
        # from code gen'ned module
        return self._function_call_spec()

    def extract_fn_name(self, ai_message: MessageNode) -> Optional[str]:
        if ai_message.ai_function_call is None:
            return None
        return ai_message.ai_function_call.name

    def extract_fn_args(
        self, ai_message: MessageNode
    ) -> Tuple[List[Any], Dict[str, Any]]:
        if (
            ai_message.ai_function_call is None
            or ai_message.ai_function_call.arguments is None
        ):
            return [], {}
        return [], ai_message.ai_function_call.arguments

    def should_call_function(self, ai_message: MessageNode) -> bool:
        fn_name = self.extract_fn_name(ai_message=ai_message)
        if fn_name:
            return True
        logger.debug("No AI function calling requested")
        return False

    def call_fn_by_name(self, fn_name: str, *args, **kwargs) -> Tuple[Any, str]:
        evt_obj_type = cast(CreatorBase, self._event_obj_type)
        event_obj = evt_obj_type.create(function_name=fn_name, **kwargs)

        self._event_node._event_obj = (  # pylint: disable=protected-access
            event_obj
        )
        logger.debug(
            _optionally_format_colorama("Parsed event:", True, Fore.RED)
        )
        logger.debug(
            "\n".join(
                [
                    f"{k}: {str(v)} ({type(v)})"
                    for k, v in formatted_dict((event_obj.model_dump())).items()  # type: ignore
                ]
            )
        )
        # The object returned by the function must have a reasonable __str__ to be useful.
        k_v = ", ".join(f"{k}={repr(v)}" for k, v in dict(event_obj).items())  # type: ignore
        return event_obj, f"{fn_name}({k_v})"
