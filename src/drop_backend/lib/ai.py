# MIT License

# Copyright (c) 2023 Sidharth Gupta
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import logging
import traceback
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
    cast,
)

import openai
from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from ..model.ai_conv_types import (
    AIFunctionCall,
    EventNode,
    InterrogationProtocol,
    MessageNode,
    Role,
)
from .event_node_manager import BaseEventManager

logger = logging.getLogger(__name__)


# Requirements
# 1. All messages will be preserved in the _context variable so we can save them.
# 2. Able to extract specific features from a Event after they are missed by the AI.
# The way llama index does this is by using fixed generators like QandA


# Parallelization of requests.
# Dealing with error: Each task has a task ID. We need to keep of which tasks completed
#
# Right now only open AI is supported, but this could be extended to other APIs.


class AIDriver:
    """Core generator that acts as a layer between the client code and the AI API.
    The generator simplifies the communication with OpenAI API in a few ways:
    1. It comminicates with the client API but its highly decoupled from that
    code: The client code only deals with the construction of the message and
    serialization of AI responses, while this code only takes care of
    maintaining context and communicating with the AI.

    2. It is also easy to "replay" events using user_messages_node variables that can
    hold all the messages.

    3. It also supports Human in Loop messages to be sent to the AI after its response
    using the interrogative_message variable.
    """

    def __init__(self, ai: AltAI, event_manager: BaseEventManager):
        self._ai = ai
        self._event_manager = event_manager

    def drive(
        self, events: List[str]
    ) -> Generator[
        EventNode | ValidationError | MessageNode,
        List[MessageNode],
        Literal["Done"],
    ]:
        # Event <--1--*--> Message
        #
        for event in events:
            event_node = self._event_manager.create_event_node(event)

            # more than one messages during replay.
            user_message_nodes = yield event_node
            assert isinstance(user_message_nodes, list)
            assert len(user_message_nodes) > 0
            context = []
            while True:
                for user_message_node in user_message_nodes:
                    context.append(user_message_node)
                try:
                    msg_from_ai = self._ai.send(context)
                except ValidationError as exc:
                    stack_trace = traceback.format_exc()
                    logger.error(
                        "Pydantic validation error in sending message to AI: %s.\n Trace: %s",
                        exc.json(),
                        stack_trace,
                    )
                    yield exc
                    break
                context.append(msg_from_ai)

                # Possible interrogation follows the Himan in loop interation
                interrogative_messages = yield msg_from_ai
                if interrogative_messages is None:
                    # We don't want to interrogate the AI for this message, so we break.
                    # print('....')
                    break
                else:
                    assert (
                        isinstance(interrogative_messages[-1], MessageNode)
                        and interrogative_messages[-1].role == Role.user
                    )
                    user_message_nodes = interrogative_messages
        return "Done"


# TODO: consider moving this to be method of AIDriver class
def driver_wrapper(
    events: List[str],
    system_message: MessageNode,
    ai_driver: AIDriver,
    # event_manager manages function calling over AI function calling API and
    # then call function(s) over the responses.
    event_manager: BaseEventManager,
    # The callback that can given an EventNode give you the raw string
    # message content used in user messages to the AI.
    user_message_prompt_fn: Callable[[EventNode], str],
    interrogation_protocol: Optional[InterrogationProtocol] = None,
) -> Generator[Tuple[EventNode, Optional[ValidationError]], None, None]:
    """
    # TODO: Probably make this part of the AIDriver class, since its tightly coupled to that.
    Drives the AIDriver by sending it a System message + User message at first then
    it can send .
    Maintains history of the message linked to the processing of the event.
    """
    driver_gen = ai_driver.drive(events)
    event_node = driver_gen.send(None)  # type: ignore
    while True:
        # Send the system prompt every time.
        try:
            logger.debug(">>")
            assert isinstance(event_node, EventNode), f"{type(event_node)}"
            # An event is started
            if not event_node.history:
                event_node.history = []
            event_node.history.append(system_message)
            # The function call should happen if its the last message from the user only.
            # 1. Should a function be called?

            (
                message_function_call_spec,
                explicit_fn_call,
            ) = event_manager.get_function_call_spec()
            user_message = MessageNode(
                role=Role.user,
                message_content=user_message_prompt_fn(event_node),
                functions=message_function_call_spec,
                explicit_fn_call=explicit_fn_call,  # mypy ignore
            )
            event_node.history.append(user_message)

            logger.debug("PreSend")

            ai_message_or_error = driver_gen.send(
                [system_message, user_message]
            )
            if isinstance(ai_message_or_error, ValidationError):
                # TODO: Handle other types of errors that cannot be retried
                yield event_node, ai_message_or_error
            else:
                ai_message = cast(MessageNode, ai_message_or_error)
                assert isinstance(ai_message, MessageNode)
                logger.debug("PostSend")
                event_node.history.append(ai_message)
                _process_ai_function_call_helper(
                    ai_message,
                    event_node,
                    event_manager,
                )
                logger.debug(">>>")
                if ai_message.message_content:
                    logger.debug(
                        "Got message_content from AI:\n%s",
                        ai_message.message_content,
                    )
                # hook to interact with anything
                # Human interaction with AI for debugging, AI Agents what have you.
                if interrogation_protocol is not None:
                    interrogation_message = (
                        interrogation_protocol.get_interrogation_message(
                            event_node
                        )
                    )
                    while interrogation_message is not None:
                        interrogation_subcontext_to_ai: List[MessageNode] = []
                        if event_node.history[-1].role == Role.function:
                            interrogation_subcontext_to_ai.append(
                                event_node.history[-1]
                            )
                        interrogation_subcontext_to_ai.append(
                            interrogation_message
                        )
                        assert interrogation_message.role == Role.user
                        if interrogation_message.metadata:
                            if (
                                interrogation_message.metadata.get(
                                    "should_call_ai_again", None
                                )
                                is True
                            ):
                                interrogation_message.functions = (
                                    message_function_call_spec
                                )
                                interrogation_message.explicit_fn_call = (
                                    explicit_fn_call
                                )

                            elif (
                                interrogation_message.metadata.get(
                                    "should_call_ai_again", None
                                )
                                is False
                            ):
                                interrogation_message.functions = None
                                interrogation_message.explicit_fn_call = None

                        ai_message = driver_gen.send(
                            interrogation_subcontext_to_ai
                        )  # type: ignore
                        assert (
                            isinstance(ai_message, MessageNode)
                            and ai_message.role == Role.assistant
                        )
                        event_node.history.append(interrogation_message)

                        event_node.history.append(ai_message)
                        _process_ai_function_call_helper(
                            ai_message,
                            event_node,
                            event_manager,
                        )
                        interrogation_message = (
                            interrogation_protocol.get_interrogation_message(
                                event_node
                            )
                        )
                yield event_node, None
                event_node = driver_gen.send(None)  # type: ignore

        except StopIteration as excinfo:
            assert (
                excinfo.value == "Done"
            ), f"Expected StopIteration('Done') instead got: `{excinfo}`"
            logger.debug(excinfo)
            break


def _process_ai_function_call_helper(
    ai_message: MessageNode,
    event_node: EventNode,
    event_manager: BaseEventManager,
):
    (
        event_obj,
        fn_call_result_str,
    ) = event_manager.try_call_fn_and_set_event(ai_message)
    if event_obj:
        assert event_node.history is not None
        assert ai_message.ai_function_call is not None
        event_node.history.append(
            MessageNode(
                role=Role.function,
                ai_function_call_result=fn_call_result_str,
                ai_function_call_result_name=ai_message.ai_function_call.name,
            )
        )


class AltAI:
    """
    Alternative to the AI class that calls the OpenAI API which works better with the Driver.
    """

    def __init__(
        self, model: str = "gpt-3.5-turbo-1106", temperature: float = 0.1
    ):
        self.temperature = temperature
        try:
            openai.Model.retrieve(model)
            logger.info("Using model %s", model)
            self.model = model
        except openai.InvalidRequestError:
            logger.warning(
                "Model %s not available for provided API key. Reverting to gpt-4.",
                model,
            )
            self.model = "gpt-4"

    def _send_with_function(  #  type: ignore # pylint: disable=no-self-argument
        send_fn: Callable[
            [
                AltAI,
                List[Dict[str, Any]],
                Optional[List[Dict[str, Any]]],
                Optional[Union[str, Dict[str, str]]],
            ],
            MessageNode,
        ]
    ) -> Callable[[Any, List[MessageNode]], MessageNode]:
        """
        Custom logic to send a message to the AI and then send the function call if requested.
        """

        def wrapper(slf, context: List[MessageNode]):
            context_messages = [
                i for i in EventNode.context_to_openai_api_messages(context)
            ]
            functions = None
            explicit_fn_call = None
            # N2S(Ref1): Move the allowed roles with functions to a config about
            # what roles can call functions. Assume that function is only
            # called if its set to do so in the last message.
            if context_messages[-1].get("role", None) == Role.user.name:
                if "functions" in context_messages[-1]:
                    # Only call the function if it was the last guy.
                    functions = context_messages[-1].pop("functions", None)
                    explicit_fn_call = context_messages[-1].pop(
                        "explicit_fn_call", None
                    )
            else:
                raise ValueError(
                    "Last message must be from user role. Msg Stream:"
                    + "\n".join([str(i) for i in context])
                )
            try:
                val = send_fn(  # pylint: disable=not-callable
                    slf, context_messages, functions, explicit_fn_call
                )  # type: ignore
                return val
            finally:
                context_messages[-1]["functions"] = functions
                context_messages[-1]["explicit_fn_call"] = explicit_fn_call

        return wrapper

    @_send_with_function  # type: ignore
    def send(
        self,
        context_messages: List[Dict[str, Any]],
        functions: Optional[List[Dict[str, Any]]],
        explicit_fn_call: Optional[Union[str, Dict[str, str]]],
    ) -> MessageNode:
        response = self._try_completion(
            context_messages,
            functions=functions,
            function_call=explicit_fn_call,
        )
        chat, func_call = _chat_function_call_from_response(response)

        logger.debug("")
        logger.debug("Chat completion finished.")
        logger.debug("".join(chat))
        if func_call:
            logger.debug(func_call)
        logger.debug("")
        return MessageNode(
            role=Role.assistant,
            message_content="".join(chat) if chat else None,
            ai_function_call=(
                AIFunctionCall.model_validate(func_call) if func_call else None
            ),
        )

    def _try_completion(
        self,
        messages: list[dict[str, str]],
        functions: Optional[list[dict[str, Any]]] = None,
        function_call=None,
    ):
        logger.debug("Creating a new chat completion: %s", messages)
        try:
            if not functions:
                response = completion_with_backoff(
                    messages=messages,
                    stream=True,
                    model=self.model,
                    temperature=self.temperature,
                )
            else:
                response = completion_with_backoff(
                    messages=messages,
                    stream=True,
                    model=self.model,
                    functions=functions,
                    function_call=function_call or None,
                    temperature=self.temperature,
                )
        except Exception as exc:
            logger.error(
                "Error in chat completion for messages %s \n functions: %s, function_call=%s",
                str(messages),
                str(functions),
                str(function_call),
            )
            raise exc
        return response


def _chat_function_call_from_response(
    response,
) -> Tuple[List[str], Optional[Dict[str, Optional[str]]]]:
    chat: List[str] = []
    func_call = None
    for chunk in response:
        try:
            delta = chunk["choices"][0]["delta"]
            if "function_call" in delta:
                # pylint: disable=pointless-string-statement
                """
                This is what delta is like:
                {'role': 'assistant', 'content': {
                    'function_call': {'name': 'get_current_weather',
                    'arguments': '{\n  "location": "Glasgow, Scotland",\n  "format": "celsius"\n}'}
                }}
                """
                if not func_call:
                    func_call = {"name": None, "arguments": ""}
                if "name" in delta.function_call:
                    func_call["name"] = delta.function_call["name"]
                if "arguments" in delta.function_call:
                    func_call["arguments"] += delta.function_call["arguments"]
            if "content" in delta:
                # Key may be there but None
                msg = delta.get("content", "") or ""
                chat.append(msg)
        except Exception as exc:
            logger.error("Error %s for chunk: %s", chunk, exc)
            raise exc
    logger.debug("Chat: %s", chat)
    return chat, func_call


@retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(10),
    retry=retry_if_exception_type(
        (
            openai.error.RateLimitError,
            openai.error.APIConnectionError,
            openai.error.ServiceUnavailableError,
            openai.error.APIError,
        )
    ),
)
def completion_with_backoff(**kwargs):
    return openai.ChatCompletion.create(**kwargs)


class NoEmbeddingsFoundException(Exception):
    pass


class EmbeddingSearch:
    def __init__(self, model: str = "text-embedding-ada-002"):
        try:
            openai.Model.retrieve(model)
            self.model = model
        except openai.InvalidRequestError as exc:
            logger.error(
                "Error occured %s Embedding Model %s not available for provided API key. ",
                exc,
                model,
            )
            raise exc

    def fetch_embeddings(self, lsts: List[str]) -> List:
        # TODO add the user parameter to the request to monitor any misuse.
        embedding_data = _fetch_embeddings(model=self.model, input=lsts)
        if (
            embedding_data
            and "data" in embedding_data
            and len(embedding_data["data"][0]) > 0
        ):
            return embedding_data["data"][0]["embedding"]
        raise NoEmbeddingsFoundException(
            "No embeddings or empty results returned from OpenAI API:",
            str(embedding_data),
        )


@retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(10),
    retry=retry_if_exception_type(
        (
            openai.error.RateLimitError,
            openai.error.APIConnectionError,
            openai.error.ServiceUnavailableError,
            openai.error.APIError,
        )
    ),
)
def _fetch_embeddings(**kwargs):
    return openai.Embedding.create(**kwargs)
