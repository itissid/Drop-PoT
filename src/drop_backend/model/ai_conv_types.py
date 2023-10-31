import enum
import json
import logging
from abc import abstractmethod
from typing import Any, Dict, Generator, List, Optional, Union

import time_uuid  # type: ignore
from pydantic import UUID1, BaseModel, Field, Json

logger = logging.getLogger(__name__)


class Role(enum.Enum):
    # pylint: disable=invalid-name
    system = "system"
    assistant = "assistant"
    user = "user"
    function = "function"

    @classmethod
    def from_string(cls, value):
        for item in cls:
            if item.value == value:
                return item
        raise ValueError(f"No {cls.__name__} member with value '{value}'")

    @classmethod
    def get_type_by_string(cls, value):
        return cls.from_string(value)


class AIFunctionCall(BaseModel):
    """
    Internal Representation of a function call.
    Example:
    {
        "name": "get_current_weather",
        "arguments":  '{\n  "location": "Glasgow, Scotland",\n  "format": "celsius"\n}'
    }

    """

    name: Optional[str] = None
    arguments: Optional[Json[Dict[str, Any]]] = None


class UserFunctionCallMode(enum.Enum):
    none = "none"
    auto = "auto"


class UserExplicitFunctionCall(BaseModel):
    name: str


class OpenAIFunctionCallSpec(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]


class MessageNode(BaseModel):
    """A generic message node. Contains a hybrid union of fields to support messages for all roles."""

    role: Role
    # Time sorted id of the message
    id: UUID1 = Field(default_factory=time_uuid.TimeUUID.with_utcnow)

    # From AI or a prompt from the user, None in case of function call
    message_content: Optional[str] = None

    # Note2Self: One idea is to have an Action node contain all the function calling variables below.
    # Then tag each event as having an action; the action would be done at run time (e.g. on attribute lookup).
    # In our case the Action node for functions is the OpenAI API call to call a function.

    # To support OpenAI function call API
    # Set for user when they want API to call a function.
    functions: Optional[List[OpenAIFunctionCallSpec]] = None
    explicit_fn_call: Optional[
        Union[UserExplicitFunctionCall, UserFunctionCallMode]
    ] = None
    # Set when AI calls a function with the name and arguments.
    ai_function_call: Optional[AIFunctionCall] = None
    # set for role: "function" from user's call to the function. Mainly used for replay or further interrogating.
    ai_function_call_result_name: Optional[str] = None
    ai_function_call_result: Optional[str] = None
    # Arbitrary meta data extracted for this message. File name, tags, versions etc.
    metadata: Optional[Dict[str, Any]] = {}

    # Key value pairs applied to message templates format string args
    template_vars: Optional[Dict[str, str]] = {}


class EventNode:
    def __init__(self, _direct=True):
        if _direct:
            raise ValueError(
                "You should use the EventFactory to instantiate this class"
            )
        self.raw_event_str: str  # Raw event data.
        self._event_obj: Optional[Any] = None
        # Consider adding a field that summarises the interrogation messages and is appended to the
        # system_prompt at runtime.
        # assume that the last message on the stack is from the user.

        # Filled in with the messages from the AI and the user, excluding the system prompt.
        self.history: Optional[List[MessageNode]] = None

        # Arbitrary meta data extracted for the event.
        self.metadata: Optional[Dict[str, Any]] = {}

    @property
    def event_obj(self):
        return self._event_obj

    @event_obj.setter
    def event_obj(self, _):
        raise AttributeError(
            "You cannot set the event_obj directly. Use the EventManager's create_event_obj to do this"
        )

    @classmethod
    def _create(cls, raw_event_str: str):
        """Shold be used from EventManager"""
        obj = EventNode(_direct=False)
        obj.raw_event_str = raw_event_str  # Raw event data.
        return obj

    @staticmethod
    def fsystem(msg: str):
        return {"role": Role.system.name, "content": msg}

    @staticmethod
    def fuser(msg: str):
        return {"role": Role.user.name, "content": msg}

    @staticmethod
    def fassistant(msg: str):
        return {"role": Role.assistant.name, "content": msg}

    @staticmethod
    def function(msg: str):
        return {"role": Role.function.name, "content": msg}

    def to_open_ai_api_messages(self) -> Generator:
        yield from EventNode.context_to_openai_api_messages(self.history or [])

    @staticmethod
    def context_to_openai_api_messages(
        context: List[MessageNode],
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Convert to a format to send to OpenAI API. Useful also for replaying.
        TODO(Sid): It might be also useful to make this class extend TypedDict instead(https://docs.pydantic.dev/latest/usage/types/dicts_mapping/#typeddict)
        so that we can validate(via pydantic) when we serialize and deserialize chat history(json) from the SQLlite database.
        """
        assert context and len(context) > 0
        if len(context) == 1:
            # *****************
            # Single message user cases.
            # *****************
            # With only one message the transformation is simple.
            # 1. If the first message is system message the transformation is
            # {
            #     "role": "system",
            #     "content": "You are an helpful AI assistant who can help me get the weather.",
            # }
            # 2. If the first message is a user message with a function call:
            # {
            #     "role": "user",
            #     "content": "What weather is it in Hoboken, NJ?",
            #     "functions": {},
            #     "function_call": {"name": "get_current_weather"} }
            # }
            # 3.  It can be an assistant message but that is odd
            #     https://asciinema.org/connect/382648b0-b78a-444b-956d-83bd1e71c9bb
            message = context[0]
            if message.role == Role.user:
                msg: Dict[str, Any] = {
                    "role": message.role.name,
                    "content": message.message_content,
                }
                if message.functions:
                    msg["functions"] = [
                        fn.model_dump(exclude_none=True)
                        for fn in message.functions
                    ]
                yield msg
            elif context[0].role == Role.assistant:
                raise ValueError(
                    "The first message is not allowed to be an assistant message!"
                )
            elif context[0].role == Role.system:
                yield EventNode.fsystem(
                    message.message_content if message.message_content else ""
                )
            else:
                raise ValueError(
                    f"Unexpected role {context[0].role} in message history of length 1"
                )
            return

            # ********************
            # Multi message use cases
            # ********************

            # 1. If a function call is the last user message and the message_node.functions is set
            # then we need to ask AI to call function,
            # User Function Call Message :
            # return ({
            #         'role: 'user',
            #         'content': 'Whats the weather like in boston',
            #     },
            #     message_node.functions,
            # )

            # 2. If user message function call is not the last message it will be followed by an assistant message (possibly with
            #     a function call), In this case we need to send to AI in the replay scenario:

            # {
            #     'role: 'user',
            #     'content': 'Whats the weather like in boston',
            # },
            # and
            # {
            #     "content": null,
            #     "function_call": {
            #         "arguments": "{\n\"location\": \"Boston, MA\"\n}",
            #         "name": "get_current_weather"
            #     },
            #     "role": "assistant"
            # }
            # and
            # {
            #     "role": "function",
            #     "name": "get_current_weather",
            #     "content": <FUNCTION RESPONSE>
            # }
            # See https://platform.openai.com/docs/guides/gpt/function-calling for more details

            # 3. If the user message(function call or not) is followed by an assistant message without a function call then we simply
            # need to send to AI:
            # {
            #     'role: 'user',
            #     'content': 'Whats the weather like in boston',

            # }
            # and
            # {
            #     'role': 'assistant',
            #     "content": "I'm sorry, but I am an AI language model and do
            #     not have real-time data. The weather in Boston can change
            #     frequently, so I would recommend checking a reliable weather
            #     website or using a weather app for the most up-to-date
            #     information."
            # }

        for message_curr, message_next in zip(context[:-1], context[1:]):
            # The use cases get a bit complex but the algo is described above.
            if message_curr.role == Role.system:
                yield {
                    "role": message_curr.role.name,
                    "content": message_curr.message_content,
                }  # No function call
            elif message_curr.role == Role.user:
                # No matter what the message_next is, we won't have a function call argument in this case.
                # If message_curr was indeed a function call then message_next should have the role `function`, unless AI did not call the function.
                assert message_curr.message_content is not None
                yield {
                    "role": message_curr.role.name,
                    "content": message_curr.message_content,
                }
            elif message_curr.role == Role.assistant:
                msg: Dict[str, Any] = {  # type: ignore
                    "role": Role.assistant.name,
                }
                if message_curr.ai_function_call:
                    # If function is called content should be Null
                    msg["content"] = message_curr.message_content
                    msg["function_call"] = {
                        "name": message_curr.ai_function_call.name,
                        "arguments": json.dumps(
                            message_curr.ai_function_call.arguments
                        ),
                    }
                    yield msg
                    # There is a message_next and if we would have stored it correctly, it was a function result; just append it here.
                    if message_next.role == Role.function:
                        yield {
                            "role": Role.function.name,
                            "name": message_next.ai_function_call_result_name,
                            "content": message_next.ai_function_call_result,
                        }
                    else:
                        # In case of a replay this could be handled and a function role could be appended to the message sequence by calling the function again.
                        err_msg = (
                            "Function call request to AI without a function result. Insert a message after this one```%s```"
                            + "\n"
                            + "with role function as a result of the call and then call me again."
                        )
                        logger.error(
                            err_msg, message_curr.model_dump_json(indent=2)
                        )
                        raise ValueError(
                            f"{err_msg}. This message is: {message_next.model_dump_json(indent=2)}"
                        )
                else:
                    msg["content"] = message_curr.message_content
                    yield msg
            elif message_curr.role == Role.function:
                logger.info(
                    "Function role and message was appeneded in the last iteration already. Ignoring"
                )
            else:
                raise ValueError(f"Unexpected role {message_curr.role}")

        # Process the last message that remains.
        if context[-1].role == Role.user:
            msg = {
                "role": context[-1].role.name,
                "content": context[-1].message_content,
            }
            if context[-1].functions:
                msg["functions"] = [
                    function.model_dump(exclude_none=True)
                    for function in context[-1].functions
                ]
                assert (
                    context[-1].explicit_fn_call is not None
                ), "Call mode must be set to be 'auto', 'none' or {'name': <function_name>}"
                msg["explicit_fn_call"] = (
                    context[-1].explicit_fn_call.model_dump()
                    if isinstance(
                        context[-1].explicit_fn_call, UserExplicitFunctionCall
                    )
                    else context[-1].explicit_fn_call.value
                )
            yield msg
        elif context[-1].role == Role.assistant:
            if context[-1].ai_function_call is not None:
                err_msg = "Function call request to AI without a function result. Add a function role with result of the call and then call me again."
                logger.error(err_msg)
                raise ValueError(err_msg)
            msg = {
                "role": context[-1].role.name,
            }
            msg["content"] = context[-1].message_content
            yield msg
        elif context[-1].role == Role.system:
            yield {
                "role": context[-1].role.name,
                "content": context[-1].message_content,
            }
        elif context[-1].role == Role.function:
            logger.info(
                "Function role was generated in the last iteration already."
            )


class InterrogationProtocol:
    @abstractmethod
    def get_interrogation_message(
        self, event: EventNode
    ) -> Optional[MessageNode]:
        ...