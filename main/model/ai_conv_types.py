import enum
from typing import Any, Dict, List, Optional

import time_uuid
from pydantic import UUID1, BaseModel, Field, Json


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

class UserExplicitFunctionCall(BaseModel):
    name: str

class MessageNode(BaseModel):
    """A generic message node"""
    role: Role
    # Time sorted id of the message
    id: UUID1 = Field(default_factory=time_uuid.TimeUUID.with_utcnow)

    # From AI or a prompt from the user, None in case of function call
    message_content: Optional[str] = None

    # To support OpenAI function call API
    # Set for user when they want API to call a function.
    message_function_call: Optional[Dict[str, Any]] = None
    explicit_fn_call: bool = False
    explicit_fn_call_spec: Optional[UserExplicitFunctionCall] = None
    # Set when AI calls a function.
    ai_function_call_result: Optional[AIFunctionCall] = None

    # Arbitrary meta data extracted for this message. File name, tags, versions etc.
    metadata: Optional[Dict[str, Any]] = {}

    # Key value pairs applied to message templates format string args
    template_vars: Optional[Dict[str, str]] = {}


class EventNode(BaseModel):
    raw_event_str: str  # Raw event data.
    # Consider adding a field that summarises the interrogation messages and is appended to the
    # system_prompt at runtime.
    # assume that the last message on the stack is from the user.

    # TODO: Add validation to always have length >= 1 messages
    # Filled in with the messages from the AI and the user, excluding the system prompt.
    history: Optional[List[MessageNode]] = None
    # Arbitrary meta data extracted for the event.
    metadata: Optional[Dict[str, Any]] = {}

    def to_open_ai_api_messages(self) -> List[Dict[str, str]]:
        """
        Convert to a format to send to OpenAI API.
        Messages from AI API:
        {role: user, content: ..., }
        {role: assistant, content: ..., function_call: {name: str|None, arguments: ...}}}

        Messages need to be tagged with metadata before sending to the AI API: id, interrogation messages.
        0. user and assistant messages without function calls are just passed through.
        1. Assistant messages with function calls need to be changed.
        2. The function parameter does not need to be set again when calling OpenAI API with previous messages.
        3. Serialization and Deserialization to SQLLite of json.
            - For SQLLite What is the correct format of the messages array I need to to store?
                - The right thing to do here is serialize the JSON purely in the BaseModel.
                - When we need to feed it back to the AI I should post process it and convert it back.
            - For sending to the API the content needs to be a string so does the arguments field for function call.

            Case 0: Value of the assistant response does not have function.
            Case1: Value of assistant response for function is  like:
                {'role': 'assistant',
                'content': None,
                'function_call': {'name': 'get_current_weather',
                'arguments': '{\n  "location": "Glasgow, Scotland",\n  "format": "celsius"\n}'}}
                This needs to be sent back as: 
                {'role': 'assistant', 'content': {
                    'function_call': {'name': 'get_current_weather',
                    'arguments': '{\n  "location": "Glasgow, Scotland",\n  "format": "celsius"\n}'}
                }}
                {'role': 'function', 'name: "get_current_weather", "content": "<JSON Serialized string of event object>" }

                If there is an error capture its trace and store it in the 'content' of role: function's content.

                How does the nested json get serialized?



        """
        assert self.history and len(
            self.history) > 0
        messages = []
        messages.append({
            "role": "system",
            "content": self.system_prompt.format(**self.system_template_vars if self.system_template_vars else {}),
        })
        for message in self.history:
            _message: Dict[str, Any] = {
                "role": message.role.name,
            }
            if message.ai_function_call_result:
                # https://platform.openai.com/docs/guides/gpt/function-calling
                _message["role"] = Role.function.name
                _message["name"] = message.ai_function_call_result.name
                _message["content"] = ...
            else:
                assert message.message_content is not None
                _message["content"] = message.message_content.format(
                    **message.template_vars if message.template_vars else {})
            if message.message_function_call:
                pass
            messages.append(_message)
        return messages
