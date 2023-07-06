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

import openai

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

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

    def fsystem(self, msg: str):
        return {"role": "system", "content": msg}

    def fuser(self, msg: str):
        return {"role": "user", "content": msg}

    def fassistant(self, msg: str):
        return {"role": "assistant", "content": msg}

    def next(
        self,
        messages: list[dict[str, str]],
        prompt=None,
        function=None,
        explicitly_call=False,
    ):
        if prompt:
            messages += [{"role": "user", "content": prompt}]

        logger.debug(f"Creating a new chat completion: {messages}")
        try:
            if not function:
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
                    functions=[function],
                    function_call=None
                    if not explicitly_call
                    else {"name": function["name"]},
                    temperature=self.temperature,
                )
        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            raise e

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
                    print(msg, end="")
                    chat.append(msg)
            except Exception as e:
                raise e
        print(func_call)
        print()
        messages += [
            {
                "role": "assistant",
                "content": "".join(chat),
                "function_call": json.dumps(func_call),
            }
        ]
        logger.debug(f"Chat completion finished: {messages}")
        return messages


@retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(6),
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
