import unittest
from typing import Optional
from unittest.mock import Mock, patch

import time_uuid

from main.lib.ai import AIDriver, driver_wrapper
from main.model.ai_conv_types import (
    EventNode,
    InterrogationProtocol,
    MessageNode,
    Role,
)


class TestAIDriver(unittest.TestCase):
    def setUp(self):
        self._stub_uuid = time_uuid.TimeUUID.with_utcnow()
        self.contexts_captured = []  # list to store captured contexts

    def mock_altai_send(self, MockedAltAI, side_effect_fn):
        MockedAltAI().send.side_effect = side_effect_fn

    def create_driver_instance(self, MockedAltAI) -> AIDriver:
        return AIDriver(MockedAltAI())

    def create_driver_wrapper_instance(
        self,
        MockedAltAI,
        events,
        system_message,
        mock_event_formatter_fn,
        mock_function_call_spec_callable,
        interrogation_callback=None,
    ):
        return driver_wrapper(
            events,
            system_message,
            self.create_driver_instance(MockedAltAI),
            message_content_formatter=mock_event_formatter_fn,
            function_call_spec_callable=mock_function_call_spec_callable,
            interrogation_callback=interrogation_callback,
        )

    def assert_message_node(self, result_msg_node, expected_msg_node):
        self.assertEqual(
            result_msg_node.model_dump(exclude="id"),
            expected_msg_node.model_dump(exclude="id"),
        )

    def assert_event_node(
        self, event_node, expected_raw_event_str, expected_len
    ):
        self.assertIsInstance(event_node, EventNode)
        self.assertEqual(event_node.raw_event_str, expected_raw_event_str)
        self.assertEqual(len(event_node.history), expected_len)

    # Modify the module path to the actual path.

    @patch("main.lib.ai.AltAI", autospec=True)
    def test_drive_order_of_context_messages(self, MockedAltAI):
        # Mock the AI's response. You might want to mock more responses based on the events you send in.
        print("test_drive_order_of_context_messages")
        contexts_captured = []  # list to store captured contexts

        # Define a side effect function to inspect the context passed to the AI's send method.
        def side_effect_fn(context):
            # Copy the context to store its state at this point in time
            contexts_captured.append(context)
            return MessageNode(
                role=Role.assistant,
                message_content="Assistant Response",
            )

        self.mock_altai_send(MockedAltAI, side_effect_fn)

        driver = self.create_driver_instance(MockedAltAI)
        events = ["test_event"]

        drive_gen = driver.drive(events)

        # The first event should be sent and the generator should yield the event_node.
        event_node = next(drive_gen)

        self.assertIsInstance(event_node, EventNode)
        self.assertEqual(event_node.raw_event_str, events[0])

        # Sending a user message to the generator
        user_msg = MessageNode(
            role=Role.user, message_content="test_user_message_content"
        )
        result_msg_node = drive_gen.send([user_msg])

        # Assertions
        self.assertIsInstance(result_msg_node, MessageNode)
        self.assert_message_node(
            result_msg_node,
            MessageNode(
                role=Role.assistant,
                message_content="Assistant Response",
            ),
        )
        final_context = [
            MessageNode(
                role=Role.user, message_content="test_user_message_content"
            ),
            MessageNode(
                role=Role.assistant,
                message_content="Assistant Response",
            ),
        ]

        for i, j in zip(contexts_captured[0], final_context):
            self.assert_message_node(i, j)
        self.assertEqual(len(contexts_captured[0]), 2)

    @patch("main.lib.ai.AltAI", autospec=True)
    def test_driver_wrapper(self, MockedAltAI):
        # mock_event_prompt_fn, mock_event_function_param,
        """
        Send a list of events to the driver wrapper, the system_messge and a real AIDriver.
        Assert that the yielded EventNode has the messages. No function calls
        """
        print("test_driver_wrapper")
        _stub_uuid = time_uuid.TimeUUID.with_utcnow()

        def side_effect_fn(context):
            # Copy the context to store its state at this point in time
            return MessageNode(
                role=Role.assistant,
                message_content="Assistant Response",
                id=_stub_uuid,
            )

        mock_event_formatter_fn = Mock()
        mock_event_formatter_fn.return_value = "You need to parse test_event1"
        mock_function_call_spec_callable = Mock()
        mock_function_call_spec_callable.return_value = None, None

        self.mock_altai_send(MockedAltAI, side_effect_fn)
        events = ["test_event1"]
        system_message = MessageNode(
            role=Role.system, message_content="test_system_message_content"
        )
        driver_wrapper_gen = self.create_driver_wrapper_instance(
            MockedAltAI,
            events,
            system_message,
            mock_event_formatter_fn,
            mock_function_call_spec_callable,
        )
        print("Calling next(driver_wrapper_gen)")
        event_node, _ = next(driver_wrapper_gen)

        self.assert_event_node(event_node, "test_event1", 3)

        self.assertEqual(mock_event_formatter_fn.call_count, 1)
        (called_event_node,), _ = mock_event_formatter_fn.call_args
        self.assertEqual(called_event_node.raw_event_str, "test_event1")
        self.assertEqual(mock_function_call_spec_callable.call_count, 1)

        self.assertEqual(event_node.raw_event_str, "test_event1")
        self.assert_message_node(
            event_node.history[0],
            MessageNode(
                role=Role.system, message_content="test_system_message_content"
            ),
        )

        self.assert_message_node(
            event_node.history[1],
            MessageNode(
                role=Role.user, message_content="You need to parse test_event1"
            ),
        )

        self.assert_message_node(
            event_node.history[2],
            MessageNode(
                role=Role.assistant, message_content="Assistant Response"
            ),
        )

        with self.assertRaises(StopIteration):
            next(driver_wrapper_gen)

    @patch("main.lib.ai.AltAI", autospec=True)
    def test_driver_for_multiple_events(self, MockedAltAI):
        """
        Assert on message sequence for multiple events. The idea is to test
        if the expected messages are asked to the AI in the right sequence.
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

        mock_event_formatter_fn = Mock()
        mock_function_call_spec_callable = Mock()

        mock_event_formatter_fn.side_effect = [
            "You need to parse test_event1",
            "You need to parse test_event2",
        ]
        mock_function_call_spec_callable.return_value = None, None
        MockedAltAI().send.side_effect = side_effect_fn
        events = ["test_event1", "test_event2"]
        system_message = MessageNode(
            role=Role.system, message_content="test_system_message_content"
        )
        driver_wrapper_gen = self.create_driver_wrapper_instance(
            MockedAltAI,
            events,
            system_message,
            mock_event_formatter_fn,
            mock_function_call_spec_callable,
        )

        print("Calling next(driver_wrapper_gen)")
        event_node, _ = next(driver_wrapper_gen)
        self.assert_event_node(event_node, "test_event1", 3)

        print("Calling next(driver_wrapper_gen)")
        event_node_2, _ = next(driver_wrapper_gen)
        self.assert_event_node(event_node_2, "test_event2", 3)
        self.assert_message_node(
            event_node_2.history[1],
            MessageNode(
                role=Role.user, message_content="You need to parse test_event2"
            ),
        )

    @patch("main.lib.ai.AltAI", autospec=True)
    def test_interrogation(self, MockedAltAI):
        print("test_driver_for_multiple_events")
        _stub_uuid = time_uuid.TimeUUID.with_utcnow()

        class MockInterrogationProtocol(InterrogationProtocol):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._i = 0
                self.call_count = 0

            def get_interrogation_message(
                self, event: EventNode
            ) -> Optional[MessageNode]:
                self.call_count += 1
                if self._i == 0:
                    self._i += 1
                    return MessageNode(
                        message_content="Are you high?",
                        role=Role.user,
                        id=_stub_uuid,
                    )
                return None

        mock_interrogation_callback = MockInterrogationProtocol()

        def side_effect_fn(context):
            # Copy the context to store its state at this point in time
            return MessageNode(
                role=Role.assistant,
                message_content="Assistant Response",
                id=_stub_uuid,
            )

        mock_event_formatter_fn = Mock()
        mock_function_call_spec_callable = Mock()
        mock_event_formatter_fn.side_effect = [
            "You need to parse test_event1",
            "You need to parse test_event2",
        ]
        mock_function_call_spec_callable.return_value = None, None
        MockedAltAI().send.side_effect = side_effect_fn
        events = ["test_event1", "test_event2"]
        system_message = MessageNode(
            role=Role.system, message_content="test_system_message_content"
        )
        driver_wrapper_gen = self.create_driver_wrapper_instance(
            MockedAltAI,
            events,
            system_message,
            mock_event_formatter_fn,
            mock_function_call_spec_callable,
            interrogation_callback=mock_interrogation_callback,
        )

        print("Calling next(driver_wrapper_gen)")
        event_node, _ = next(driver_wrapper_gen)

        self.assert_event_node(event_node, "test_event1", 5)

        self.assert_message_node(
            event_node.history[3],
            MessageNode(role=Role.user, message_content="Are you high?"),
        )
        self.assert_message_node(
            event_node.history[4],
            MessageNode(
                role=Role.assistant, message_content="Assistant Response"
            ),
        )

        # Second time this message was null
        self.assertEqual(mock_interrogation_callback.call_count, 2)

        print("Calling next(driver_wrapper_gen)")
        event_node_2, _ = next(driver_wrapper_gen)
        self.assert_event_node(event_node_2, "test_event2", 3)
        self.assert_message_node(
            event_node_2.history[1],
            MessageNode(
                role=Role.user, message_content="You need to parse test_event2"
            ),
        )
        self.assertEqual(mock_interrogation_callback.call_count, 3)
