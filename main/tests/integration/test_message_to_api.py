import json
import os
import unittest
from typing import Any, List, Optional, Tuple

import ipdb
import openai
from dotenv import load_dotenv

from main.lib.ai import AIDriver, AltAI, driver_wrapper
from main.model.ai_conv_types import (EventNode, InterrogationProtocol,
                                      MessageNode,
                                      OpenAIFunctionCallParameters)
from main.model.ai_conv_types import OpenAIFunctionCallProperty as p
from main.model.ai_conv_types import (OpenAIFunctionCallSpec, Role,
                                      UserExplicitFunctionCall)


def get_current_weather(location, unit="fahrenheit"):
    """Get the current weather in a given location"""
    weather_info = {
        "location": location,
        "temperature": "72",
        "unit": unit,
        "forecast": ["sunny", "windy"],
    }
    return weather_info, json.dumps(weather_info)


class TestSendToOpenAIAPI(unittest.TestCase):

    def test_replay_messages_for_function_call_are_separately_maintained(self):
        """
        - Send a user message: "Whats the weather in Boston in farenheit?" with a function call to the AI using driver_wrapper.
        - Along with the function call to the AI there should be a message with the role `function` and the call result.
        - The next message is a correction to the earlier message like "Could you specify the weather in Boston in celsius?"
        """
        # Mock out the call to AI and extract the messages and make sure the
        pass

    def test_no_function_execution(self) -> None:
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        openai.api_key = api_key
        driver = driver_wrapper(
            events=["What's the climate typically like in Boston during October"],
            system_message=MessageNode(
                role=Role.system,
                message_content="You are helpful assistant. Follow the instructions I give you. Do not respond until I ask you a question.",
            ),
            ai_driver=AIDriver(AltAI(model="gpt-3.5-turbo-16k")),
            message_content_callable=lambda x: x.raw_event_str,
            function_call_spec_callable=None,
            function_callable_for_ai_function_call=None
        )
        event = next(driver)
        self.assertEquals(len(event.history), 3)
        self.assertEquals(event.history[0].role, Role.system)
        self.assertEquals(event.history[1].role, Role.user)
        self.assertEquals(event.history[2].role, Role.assistant)
        self.assertGreaterEqual(len(event.history[2].message_content), 1)

        print(event.history[2].message_content)
        # No function call
        self.assertEqual(event.history[2].ai_function_call, None)

    def test_event_to_open_ai__user_function_mandate_is_obeyed(self) -> None:
        """If MessageNode.role == user and MessageNode.message_function_call and MessageNode.explicit_function_call_spec are not null then the 
        next message must have a role `function` with call result. The message after that is  an assistant message.

        This is done by calling the AI and getting the actual response from it.

        As an example lets test the weather function.
        """
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        openai.api_key = api_key

        functions = [OpenAIFunctionCallSpec(
            name="get_current_weather",
            description="Get the current weather in a given location",
            parameters=OpenAIFunctionCallParameters(
                type="object",
                properties=dict(
                    location=p(
                        type="string",
                        description="The city and state, e.g. San Francisco, CA",
                    ),
                    unit=p(type="string", enum=["celsius", "fahrenheit"]),
                ),
                required=["location"],
            )
        )]

        def weather_fn_call_wrapper(ai_message: MessageNode) -> Tuple[Any, str]:
            assert ai_message.ai_function_call is not None and ai_message.ai_function_call.arguments is not None
            return get_current_weather(
                location=ai_message.ai_function_call.arguments.get("location"),
                unit=ai_message.ai_function_call.arguments.get("unit"))

        driver = driver_wrapper(
            events=["What's the weather like in Boston in farenheit?"],
            system_message=MessageNode(
                role=Role.system,
                message_content="You are helpful assistant. Follow the instructions I give you. Do not respond until I ask you a question.",
            ),
            ai_driver=AIDriver(AltAI(model="gpt-3.5-turbo-16k")),
            message_content_callable=lambda x: x.raw_event_str,
            function_call_spec_callable=lambda: (functions, UserExplicitFunctionCall(
                name="get_current_weather",
            )),
            function_callable_for_ai_function_call=lambda ai_message: weather_fn_call_wrapper(
                ai_message)
        )
        event = next(driver)
        print(event.event_obj)
        print(event.history)
        self.assertEquals(len(event.history), 4)
        self.assertEquals(event.history[0].role, Role.system)
        self.assertEquals(event.history[0].message_content,
                          "You are helpful assistant. Follow the instructions I give you. Do not respond until I ask you a question.")
        self.assertEquals(event.history[1].role, Role.user)
        self.assertEquals(
            event.history[1].message_content, "What's the weather like in Boston in farenheit?")

        # MessageNode's functions is set and explicit_function_call is also set
        assert event.history[1].functions == functions
        self.assertEquals(event.history[1].explicit_fn_call, UserExplicitFunctionCall(
            name="get_current_weather"))

        self.assertEquals(event.history[2].role, Role.assistant)
        self.assertEquals(
            event.history[2].ai_function_call.name, 'get_current_weather')
        self.assertEquals(event.history[2].message_content, "")
        self.assertEquals(event.history[2].ai_function_call.model_dump(), {
                          'name': 'get_current_weather', 'arguments': {'location': 'Boston, MA', 'unit': 'fahrenheit'}})

        self.assertEquals(event.history[3].role, Role.function)
        self.assertEquals(
            event.history[3].ai_function_call_result_name, "get_current_weather")
        self.assertEquals(event.history[3].ai_function_call_result, json.dumps({
            "location": "Boston, MA",
            "temperature": "72",
            "unit": "fahrenheit",
            "forecast": ["sunny", "windy"],
        }))


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSendToOpenAIAPI)
    runner = unittest.TextTestRunner()
    try:
        runner.run(suite)
    except Exception:
        ipdb.post_mortem()
