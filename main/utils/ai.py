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
from typing import List

import openai
from tenacity import (retry, retry_if_exception_type, stop_after_attempt,
                      wait_random_exponential)

logger = logging.getLogger(__name__)


# Parallelization of requests.
# Dealing with error: Each task has a task ID. We need to keep of which tasks completed
#
# Right now only open AI is supported, but this could be extended to other APIs.
class AI:
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

    def start(self, system: str, user: str, function=None):
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        return self.next(messages, function=function)

    @staticmethod
    def fsystem(msg: str):
        return {"role": "system", "content": msg}

    @staticmethod
    def fuser(msg: str):
        return {"role": "user", "content": msg}

    @staticmethod
    def fassistant(msg: str):
        return {"role": "assistant", "content": msg}

    def next(
        self,
        messages: List[dict[str, str]],
        prompt=None,
        function=None,
        explicitly_call=False,
    ):
        if prompt:
            messages += [{"role": "user", "content": prompt}]

        response = _try_completion(messages, self.model, function=function,
                                   temperature=self.temperature, explicitly_call=explicitly_call)
        chat, func_call = _chat_function_call_from_response(response)
        print()
        logger.debug("Chat completion finished.")
        logger.debug("".join(chat))
        logger.debug(func_call)
        print()

        messages += [
            {
                "role": "assistant",
                "content": "".join(chat),
                "function_call": func_call,
            }
        ]
        return messages


def _try_completion(messages, model, function=None, temperature=0.1, explicitly_call=False):
    logger.debug(f"Creating a new chat completion: {messages}")
    try:
        if not function:
            response = completion_with_backoff(
                messages=messages,
                stream=True,
                model=model,
                temperature=temperature,
            )
        else:
            response = completion_with_backoff(
                messages=messages,
                stream=True,
                model=model,
                functions=[function],
                function_call=None
                if not explicitly_call
                else {"name": function["name"]},
                temperature=temperature,
            )
    except Exception as e:
        logger.error(f"Error in chat completion: {e}")
        raise e
    return response


def _chat_function_call_from_response(response):
    chat = []
    func_call = {
        "name": None,
        "arguments": "",
    }
    for chunk in response:
        try:
            delta = chunk["choices"][0]["delta"]
            if "function_call" in delta:
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
