import unittest
from unittest.mock import Mock, patch

import pytest
import time_uuid

from main.hoboken_girl_extraction import hoboken_girl_driver_wrapper
from main.model.ai_conv_types import EventNode, MessageNode, Role
from main.lib.ai import AIDriver

# def test_is_history_maintained():
#     pass


class TestAIDriver(unittest.TestCase):

    # Modify the module path to the actual path.
    @patch("main.lib.ai.AltAI", autospec=True)
    def test_drive_order_of_context_messages(self, MockedAltAI):
        # Mock the AI's response. You might want to mock more responses based on the events you send in.
        print('test_drive_order_of_context_messages')
        contexts_captured = []  # list to store captured contexts

        # Define a side effect function to inspect the context passed to the AI's send method.
        def side_effect_fn(context):
            # Copy the context to store its state at this point in time
            contexts_captured.append(context)
            return MessageNode(
                role=Role.assistant,
                message_content="Assistant Response",
            )

        MockedAltAI().send.side_effect = side_effect_fn

        driver = AIDriver(MockedAltAI())
        events = ["test_event"]

        drive_gen = driver.drive(events)

        # The first event should be sent and the generator should yield the event_node.
        event_node = next(drive_gen)

        self.assertIsInstance(event_node, EventNode)
        self.assertEqual(event_node.raw_event_str, events[0])

        # Sending a user message to the generator
        user_msg = MessageNode(
            role=Role.user,
            message_content="test_user_message_content"
        )
        result_msg_node = drive_gen.send([user_msg])

        # Assertions
        self.assertIsInstance(result_msg_node, MessageNode)
        self.assertEqual(result_msg_node.model_dump(exclude="id"),  MessageNode(
            role=Role.assistant,
            message_content="Assistant Response",
        ).model_dump(exclude="id"))
        final_context = [
            MessageNode(
                role=Role.user,
                message_content="test_user_message_content"
            ),
            MessageNode(
                role=Role.assistant,
                message_content="Assistant Response",
            ),
        ]

        self.assertEqual([i.model_dump(exclude="id")
                         for i in contexts_captured[0]], [i.model_dump(exclude="id") for i in final_context])
        self.assertEqual(len(contexts_captured[0]), 2)

    @patch("main.lib.ai.AltAI", autospec=True)
    @patch("main.hoboken_girl_extraction.hoboken_girl_event_function_param")
    @patch("main.hoboken_girl_extraction.default_parse_event_prompt")
    def test_driver_wrapper(self, mock_event_prompt_fn, mock_event_function_param, MockedAltAI):
        """
        Send a list of events to the driver wrapper, the system_messge and a real AIDriver.
        Asserr that the yielded EventNode has the messages
        """
        print('test_driver_wrapper')
        _stub_uuid = time_uuid.TimeUUID.with_utcnow()

        def side_effect_fn(context):
            # Copy the context to store its state at this point in time
            return MessageNode(
                role=Role.assistant,
                message_content="Assistant Response",
                id=_stub_uuid,
            )
        mock_event_prompt_fn.return_value = "You need to parse test_event1"
        mock_event_function_param.return_value = None, None

        MockedAltAI().send.side_effect = side_effect_fn
        events = ["test_event1"]
        system_message = MessageNode(
            role=Role.system, message_content="test_system_message_content")
        driver_wrapper_gen = hoboken_girl_driver_wrapper(
            events, system_message, AIDriver(MockedAltAI()))
        print("Calling next(driver_wrapper_gen)")
        event_node = next(driver_wrapper_gen)

        self.assertIsInstance(event_node, EventNode)
        self.assertEqual(len(event_node.history), 3)

        self.assertEqual(mock_event_prompt_fn.call_count, 1)
        mock_event_prompt_fn.assert_called_with(event="test_event1")
        self.assertEqual(mock_event_function_param.call_count, 1)

        self.assertEqual(event_node.raw_event_str, "test_event1")
        self.assertEqual(event_node.history[0].role, Role.system)
        self.assertEqual(
            event_node.history[0].message_content, "test_system_message_content")

        self.assertEqual(event_node.history[1].role, Role.user)
        self.assertEqual(
            event_node.history[1].message_content, "You need to parse test_event1")

        self.assertEqual(event_node.history[2].role, Role.assistant)
        self.assertEqual(
            event_node.history[2].message_content, "Assistant Response")

        with self.assertRaises(StopIteration):
            next(driver_wrapper_gen)

    @patch("main.utils.ai.AltAI", autospec=True)
    @patch("main.hoboken_girl_extraction.hoboken_girl_event_function_param")
    @patch("main.hoboken_girl_extraction.default_parse_event_prompt")
    def test_driver_for_multiple_events(self, mock_event_prompt_fn, mock_event_function_param, MockedAltAI):
        """
        Assert on message sequence for multiple events
        """
        print("test_driver_for_multiple_events")
        _stub_uuid = time_uuid.TimeUUID.with_utcnow()

        def side_effect_fn(context):
            # Copy the context to store its state at this point in time
            return MessageNode(
                role=Role.assistant,
                message_content="Assistant Response",
                id=_stub_uuid,
            )
        mock_event_prompt_fn.side_effect = [
            "You need to parse test_event1", "You need to parse test_event2"]
        mock_event_function_param.return_value = None, None
        MockedAltAI().send.side_effect = side_effect_fn
        events = ["test_event1", "test_event2"]
        system_message = MessageNode(
            role=Role.system, message_content="test_system_message_content")
        driver_wrapper_gen = hoboken_girl_driver_wrapper(
            events, system_message, AIDriver(MockedAltAI()))

        print("Calling next(driver_wrapper_gen)")
        event_node = next(driver_wrapper_gen)

        self.assertIsInstance(event_node, EventNode)
        self.assertEqual(len(event_node.history), 3)

        print("Calling next(driver_wrapper_gen)")
        event_node_2 = next(driver_wrapper_gen)
        self.assertIsInstance(event_node_2, EventNode)
        self.assertEqual(len(event_node_2.history), 3)
        self.assertEqual(event_node_2.raw_event_str, "test_event2")
        self.assertEqual(
            event_node_2.history[1].message_content, "You need to parse test_event2")

    @patch("main.utils.ai.AltAI", autospec=True)
    @patch("main.hoboken_girl_extraction.hoboken_girl_event_function_param")
    @patch("main.hoboken_girl_extraction.default_parse_event_prompt")
    def test_interrogation(self, mock_event_prompt_fn, mock_event_function_param, MockedAltAI):
        print("test_driver_for_multiple_events")
        _stub_uuid = time_uuid.TimeUUID.with_utcnow()
        mock_interrogation_callback = Mock()
        mock_interrogation_callback.side_effect = [MessageNode(
            message_content="Are you high?",
            role=Role.user,
            id=_stub_uuid,
        ), None, None, None, None]

        def side_effect_fn(context):
            # Copy the context to store its state at this point in time
            return MessageNode(
                role=Role.assistant,
                message_content="Assistant Response",
                id=_stub_uuid,
            )
        mock_event_prompt_fn.side_effect = [
            "You need to parse test_event1", "You need to parse test_event2"]
        mock_event_function_param.return_value = None, None
        MockedAltAI().send.side_effect = side_effect_fn
        events = ["test_event1", "test_event2"]
        system_message = MessageNode(
            role=Role.system, message_content="test_system_message_content")
        driver_wrapper_gen = hoboken_girl_driver_wrapper(
            events,
            system_message,
            AIDriver(MockedAltAI()),
            interrogation_callback=mock_interrogation_callback)

        print("Calling next(driver_wrapper_gen)")
        event_node = next(driver_wrapper_gen)

        self.assertIsInstance(event_node, EventNode)
        self.assertEqual(len(event_node.history), 5)
        self.assertEqual(event_node.raw_event_str, "test_event1")
        self.assertEqual(event_node.history[3].role, Role.user)
        self.assertEqual(event_node.history[3].message_content, "Are you high?")
        self.assertEqual(event_node.history[4].role, Role.assistant)
        self.assertEqual(event_node.history[4].message_content, "Assistant Response")

        self.assertEqual(mock_interrogation_callback.call_count, 2) # Second time this message was null

        print("Calling next(driver_wrapper_gen)")
        event_node_2 = next(driver_wrapper_gen)
        self.assertIsInstance(event_node_2, EventNode)
        self.assertEqual(len(event_node_2.history), 3)
        self.assertEqual(event_node_2.raw_event_str, "test_event2")
        self.assertEqual(event_node_2.history[1].message_content, "You need to parse test_event2")
        self.assertEqual(mock_interrogation_callback.call_count, 3)
