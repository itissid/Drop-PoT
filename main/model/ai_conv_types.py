import enum
import json
import logging
from abc import abstractmethod
from typing import Any, Dict, Generator, List, Optional, Union

import time_uuid
from pydantic import UUID1, BaseModel, Field, Json, validator

from main.model.types import Event

logger = logging.getLogger(__name__)


class Role(enum.Enum):
    system = 'system'
    assistant = 'assistant'
    user = 'user'
    function = 'function'

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
    arguments: Optional[Json] = None


class UserFunctionCallMode(enum.Enum):
    none = "none"
    auto = "auto"


class UserExplicitFunctionCall(BaseModel):
    name: str


class OpenAIFunctionCallProperty(BaseModel):
    type: str
    # Use print(property.dict(exclude_none=True)) to exclude Optional fields.
    items: Optional['OpenAIFunctionCallProperty'] = None
    enum: Optional[List[str]] = None

    @validator('items', 'enum', pre=True, allow_reuse=True)
    def prevent_none(cls, v):
        assert v is not None, '`items` and `enum` may not be None'
        return v


class OpenAIFunctionCallParameters(BaseModel):
    type: str
    properties: Dict[str, OpenAIFunctionCallProperty]
    required: List[str]


class OpenAIFunctionCallSpec(BaseModel):
    name: str
    description: str
    parameters: OpenAIFunctionCallParameters


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
    explicit_fn_call: Optional[Union[UserExplicitFunctionCall,
                                     UserFunctionCallMode]] = None
    # Set when AI calls a function.
    ai_function_call: Optional[AIFunctionCall] = None
    # set for role: function from user's call to the function. Mainly used for replay or further interrogating.
    ai_function_call_result_name: Optional[str] = None
    ai_function_call_result: Optional[str] = None
    # Arbitrary meta data extracted for this message. File name, tags, versions etc.
    metadata: Optional[Dict[str, Any]] = {}

    # Key value pairs applied to message templates format string args
    template_vars: Optional[Dict[str, str]] = {}


class EventNode(BaseModel):
    raw_event_str: str  # Raw event data.
    event_obj: Optional[Event] = None
    # Consider adding a field that summarises the interrogation messages and is appended to the
    # system_prompt at runtime.
    # assume that the last message on the stack is from the user.

    # TODO: Add validation to always have length >= 1 messages
    # Filled in with the messages from the AI and the user, excluding the system prompt.
    history: Optional[List[MessageNode]] = None
    # Arbitrary meta data extracted for the event.
    metadata: Optional[Dict[str, Any]] = {}

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
    def context_to_openai_api_messages(context: List[MessageNode]) -> Generator:
        """
        Convert to a format to send to OpenAI API. Useful also for replaying.
        """
        assert context and len(context) > 0
        if len(context) == 1:
            """
                *****************
                Single message user cases.
                *****************
                With only one message the transformation is simple.
                1. If the first message is system message the transformation is 
                {
                    "role": "system",
                    "content": "You are an helpful AI assistant who can help me get the weather.",                    
                }
                2. If the first message is a user message with a function call:
                {
                    "role": "user",
                    "content": "What weather is it in Hoboken, NJ?",
                    "functions": {},
                    "function_call": {"name": "get_current_weather"} }
                }
                3.  It can be an assistant message but that is odd
                    https://asciinema.org/connect/382648b0-b78a-444b-956d-83bd1e71c9bb
            """
            message = context[0]
            if message.role == Role.user:
                msg: Dict[str, Any] = {
                    "role": message.role.name,
                    "content": message.message_content,
                }
                if message.functions:
                    msg["functions"] = [fn.model_dump(
                        exclude_none=True) for fn in message.functions]
                yield msg
            elif context[0].role == Role.assistant:
                raise ValueError(
                    "The first message is not allowed to be an assistant message!")
            elif context[0].role == Role.system:
                yield EventNode.fsystem(message.message_content if message.message_content else '')
            else:
                raise ValueError(
                    f"Unexpected role {context[0].role} in message history of length 1")
            return

        """
            ********************
            Multi message use cases
            ********************

            1. If a function call is the last user message and the message_node.functions is set 
            then we need to ask AI to call function, 
            User Function Call Message : 
            return ({
                    'role: 'user',
                    'content': 'Whats the weather like in boston',
                }, 
                message_node.functions,
            )
            
            2. If user message function call is not the last message it will be followed by an assistant message with 
                a function call, In this case we need to send to AI(this is the replay scenario):

            {
                    'role: 'user',
                    'content': 'Whats the weather like in boston',
            },
            and 
            {
                "content": null,
                "function_call": {
                    "arguments": "{\n\"location\": \"Boston, MA\"\n}",
                    "name": "get_current_weather"
                },
                "role": "assistant"
            }
            and 
            {
                "role": "function",
                "name": "get_current_weather",
                "content": <FUNCTION RESPONSE>
            }
            See https://platform.openai.com/docs/guides/gpt/function-calling for more details

            3. If the user message(function call or not) is followed by an assistant message without a function call then we simply 
            need to send to AI:
            {
                    'role: 'user',
                    'content': 'Whats the weather like in boston',

            }
            and
            {
                'role': 'assistant',
                "content": "I'm sorry, but I am an AI language model and do
                not have real-time data. The weather in Boston can change
                frequently, so I would recommend checking a reliable weather
                website or using a weather app for the most up-to-date
                information."
            }

            """
        for message_curr, message_next in zip(context[:-1], context[1:]):
            """ The use cases get a bit complex"""
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

                msg: Dict[str, Any] = {
                    "role": Role.assistant.name,
                }
                if message_curr.ai_function_call:
                    # If function is called content should be Null
                    msg["content"] = message_curr.message_content
                    msg["function_call"] = {
                        "name": message_curr.ai_function_call.name,
                        "arguments": json.dumps(message_curr.ai_function_call.arguments),
                    }
                    yield msg
                    # There is a message_next and we would have stored it correctly it was a function result; just append it here.
                    if message_next.role == Role.function:
                        yield {
                            "role": Role.function.name,
                            "name": message_next.ai_function_call_result_name,
                            "content": message_next.ai_function_call_result,
                        }
                    else:
                        logger.warn(
                            f"Expected a function result message but did not find one in {message_next}"
                        )
                else:
                    msg["content"] = message_curr.message_content
                    yield msg
            elif message_curr.role == Role.function:
                logger.info(
                    "Function role was appeneded in the last iteration already.")
            else:
                raise ValueError(f"Unexpected role {message_curr.role}")

        # Process the last message.
        if context[-1].role == Role.user:
            msg = {
                "role": context[-1].role.name,
                "content": context[-1].message_content,
            }
            if context[-1].functions:
                msg["functions"] = [function.model_dump(
                    exclude_none=True) for function in context[-1].functions]
                assert context[
                    -1].explicit_fn_call is not None, "Call mode must be set to be 'auto', 'none' or {'name': <function_name>}"
                msg["explicit_fn_call"] = (context[-1].explicit_fn_call.model_dump()
                                           if isinstance(context[-1].explicit_fn_call, UserExplicitFunctionCall)
                                           else context[-1].explicit_fn_call.value)
            yield msg
        elif context[-1].role == Role.assistant:
            msg = {
                "role": context[-1].role.name,
            }
            if context[-1].ai_function_call:
                logger.warn(
                    "Function call request to AI without a function result message following it. The function result message should have been added by driver already.")
                msg["content"] = None
                msg["function_call"] = {
                    "name": context[-1].ai_function_call.name,
                    "arguments": json.dumps(context[-1].ai_function_call.arguments),
                }
                yield msg

                yield {
                    "role": Role.function.name,
                    "name": context[-1].ai_function_call_result_name,
                    "content": context[-1].ai_function_call_result,
                }
            else:
                msg["content"] = context[-1].message_content
                yield msg
        elif context[-1].role == Role.system:
            yield {
                "role": context[-1].role.name,
                "content": context[-1].message_content,
            }
        elif context[-1].role == Role.function:
            logger.info(
                "Function role was generated in the last iteration already.")


class InterrogationProtocol:
    @abstractmethod
    def get_interrogation_message(self, event: EventNode) -> Optional[MessageNode]:
        ...

    pass
