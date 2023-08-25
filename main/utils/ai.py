# MIT License

# Copyright (c) 2023 Anton Osika
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

import json
import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import openai
from colorama import Fore
from pydantic import UUID1, BaseModel, Field, Json
from tenacity import (retry, retry_if_exception_type, stop_after_attempt,
                      wait_random_exponential)

from main.model.ai_conv_types import (AIFunctionCall, EventNode, MessageNode,
                                      Role)

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

    def __init__(self, ai: AltAI):
        self._ai = ai

    def drive(self, events: List[str]):
        # Event <--1--*--> Message
        for event in events:
            event_node = EventNode(raw_event_str=event)

            # more than one messages during replay.
            user_message_nodes: List[MessageNode] = yield event_node
            assert len(user_message_nodes) > 0
            context = []
            while True:
                for user_message_node in user_message_nodes:
                    context.append(user_message_node)

                msg_from_ai = self._ai.send(context)
                context.append(msg_from_ai)

                # Possible interrogation follows the Himan in loop interation
                interrogative_message = yield msg_from_ai
                if interrogative_message is None:
                    # We don't want to interrogate the AI for this message, so we break.
                    # print('....')
                    break
                else:
                    print(f'.....{interrogative_message}')
                    assert isinstance(
                        interrogative_message, MessageNode) and interrogative_message.role == Role.user
                    user_message_nodes = [interrogative_message]


def driver_wrapper(
        events: List[str],
        system_message: MessageNode,
        ai_driver: AIDriver,
        # The callback that can given an EventNode give you the raw string
        # message content used in user messages to the AI.
        message_content_callable: Callable[[EventNode], str],
        # A callback that gets you the function call spec for passing to OpenAI:
        # https://platform.openai.com/docs/guides/gpt/function-calling
        # TODO: Make these types less verbose.
        function_call_spec_callable: Callable[[
        ], Tuple[Optional[List[Dict[str, Any]]], Optional[Union[Dict[str, str], str]]]],
        # A callback to get the result of the function that the AI recommended you call.
        function_callable_for_ai_function_call: Callable[[
            MessageNode], Tuple[Optional[Any], Optional[str]]],
        interrogation_callback: Callable[[
            EventNode], Optional[MessageNode]] = lambda x: None

):
    """
    Drives the AIDriver by sending it a System message + User message at first then 
    it can send .
    Maintains history of the message linked to the processing of the event.
    """
    driver_gen = ai_driver.drive(events)
    event_node = driver_gen.send(None)
    # for event_node in driver_gen:
    while True:
        # Send the system prompt every time.
        try:
            print('>>')
            assert isinstance(event_node, EventNode), f'{type(event_node)}'
            # An event is started
            if not event_node.history:
                event_node.history = []
            event_node.history.append(system_message)
            # The function call should happen if its the last message from the user only.
            message_function_call_spec, explicit_fn_call = function_call_spec_callable(
            ) if function_call_spec_callable is not None else (None, None)
            user_message = MessageNode(
                role=Role.user,
                message_content=message_content_callable(event_node),
                functions=message_function_call_spec,
                explicit_fn_call=explicit_fn_call,  # mypy ignore
            )
            event_node.history.append(user_message)

            print('PreSend')
            ai_message = driver_gen.send([system_message, user_message])
            print('PostSend')

            event_node.history.append(ai_message)

            if ai_message.ai_function_call:
                fn_call_result, fn_call_result_str = function_callable_for_ai_function_call(
                    ai_message)
                event_node.history.append(MessageNode(
                    role=Role.function,
                    ai_function_call_result=fn_call_result_str,
                    ai_function_call_result_name=ai_message.ai_function_call.name
                ))
                event_node.event_obj = fn_call_result
            print('>>>')

            print(f"Got message from AI:\n {ai_message.message_content}")
            # Human interaction with AI if set is managed here.
            if interrogation_callback is not None:
                interrogation_message = interrogation_callback(event_node)
                # User is now conversing with the AI, trying to get it to fix its responses.
                while interrogation_message is not None:
                    assert interrogation_message.role == Role.user
                    # TestMe: Is function calling working here? 
                    ai_message = driver_gen.send(interrogation_message)
                    event_node.history.append(interrogation_message)
                    assert isinstance(
                        ai_message, MessageNode) and ai_message.role == Role.assistant

                    event_node.history.append(ai_message)
                    interrogation_message = interrogation_callback(event_node)
            yield event_node
            event_node = driver_gen.send(None)

        except StopIteration as excinfo:
            logger.debug(excinfo)
            break


class AltAI:
    """
    Alternative to the AI class that calls the OpenAI API which works better with the Driver.
    """

    def __init__(self, model: str = "gpt-4", temperature: float = 0.1):
        self.temperature = temperature
        try:
            openai.Model.retrieve(model)
            self.model = model
        except openai.InvalidRequestError:
            print(
                f"Model {model} not available for provided API key. Reverting "
                "to gpt-3.5-turbo-16k. Sign up for the GPT-4 wait list here: "
                "https://openai.com/waitlist/gpt-4-api"
            )
            self.model = "gpt-3.5-turbo-16k"

    def _send_with_function(  # type: ignore
            send_fn: Callable[[AltAI, List[MessageNode]], MessageNode]
    ) -> Callable[[Any, List[MessageNode]], MessageNode]:
        """
        Custom logic to send a message to the AI and then send the function call if requested.
        """
        def wrapper(slf, context: List[MessageNode]):
            context_messages = [
                i for i in EventNode.context_to_openai_api_messages(context)]
            functions = None
            explicit_fn_call = None
            # N2S(Ref1): Move the allowed roles with functions to a config
            if context_messages[-1].get("role", None) == Role.user.name:
                if "functions" in context_messages[-1]:
                    # Only call the function if it was the last guy.
                    functions = context_messages[-1].pop("functions", None)
                    explicit_fn_call = context_messages[-1].pop(
                        "explicit_fn_call", None)
            else:
                raise ValueError(
                    "Last message must be from user role. Msg Stream:"+'\n'.join([str(i) for i in context]))
            try:
                # type: ignore
                return send_fn(slf, context_messages, functions, explicit_fn_call)
            finally:
                context_messages[-1]["functions"] = functions
                context_messages[-1]["explicit_fn_call"] = explicit_fn_call

        return wrapper

    @_send_with_function  # type: ignore
    def send(self, context_messages: List[Dict[str, str]], functions, explicit_fn_call) -> MessageNode:

        response = self._try_completion(
            context_messages,
            functions=functions,
            fn_call=explicit_fn_call
        )
        chat, func_call = _chat_function_call_from_response(response)

        print()
        logger.debug("Chat completion finished.")
        logger.debug("".join(chat))
        if func_call:
            logger.debug(func_call)
        print()
        return MessageNode(
            role=Role.assistant,
            message_content="".join(chat) if chat else None,
            ai_function_call=(AIFunctionCall.model_validate(func_call)
                              if func_call else None)
        )

    def _try_completion(self, messages, functions=None, fn_call=None):
        logger.debug(f"Creating a new chat completion: {messages}")
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
                    function_call=fn_call or None,
                    temperature=self.temperature,
                )
        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            raise e
        return response


def _chat_function_call_from_response(response):
    chat = []
    func_call = None
    for chunk in response:
        try:
            delta = chunk["choices"][0]["delta"]
            if "function_call" in delta:
                """
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
                    func_call["arguments"] += delta.function_call[
                        "arguments"
                    ]
            if "content" in delta:
                msg = (
                    delta.get("content", "") or ""
                )  # Key may be there but None
                chat.append(msg)
        except Exception as e:
            raise e
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


class EmbeddingSearch:
    def __init__(self, model: str = "text-embedding-ada-002"):
        try:
            openai.Model.retrieve(model)
            self.model = model
        except openai.InvalidRequestError as e:
            logger.warn(
                f"Embedding Model {model} not available for provided API key. "
            )
            logger.exception(e)
            raise e

    def fetch_embeddings(self, lsts: List[str]) -> List:
        # TODO add the user parameter to the request to monitor any misuse.
        embedding_data = _fetch_embeddings(model=self.model, input=lsts)
        if embedding_data and 'data' in embedding_data and len(embedding_data['data'][0]) > 0:
            return embedding_data['data'][0]['embedding']
        else:
            raise Exception(
                f"No embeddings or empty results returned from OpenAI API:\n{str(embedding_data)})")


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
