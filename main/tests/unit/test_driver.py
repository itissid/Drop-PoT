import unittest
from unittest.mock import patch

from main.hoboken_girl_extraction import driver_wrapper
from main.model.ai_conv_types import EventNode, MessageNode, Role
from main.utils.ai import AIDriver, AltAI

# def test_is_history_maintained():
#     pass


class TestAIDriver(unittest.TestCase):

    # Modify the module path to the actual path.
    @patch("main.utils.ai.AltAI", autospec=True)
    def test_drive_order_of_context_messages(self, MockedAltAI):
        # Mock the AI's response. You might want to mock more responses based on the events you send in.
        contexts_captured = []  # list to store captured contexts

        # Define a side effect function to inspect the context passed to the AI's send method.
        def side_effect_fn(context):
            # Copy the context to store its state at this point in time
            contexts_captured.append(context)
            return {"role": "assistant", "content": "Assistant Response"}

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
        final_context = [
            {"role": "user", "content": "test_user_message_content"},
            {"role": "assistant", "content": "Assistant Response"},
        ]

        self.assertEqual(contexts_captured[0], final_context)
        self.assertEqual(len(contexts_captured[0]), 2)

    @patch("main.utils.ai.AltAI", autospec=True)
    def test_driver_wrapper(self, MockedAltAI):
        """
        Send a list of events to the driver wrapper, the system_messge and a real AIDriver.
        Asserr that the yielded EventNode has the messages
        """
        def side_effect_fn(context):
            # Copy the context to store its state at this point in time
            return {"role": "assistant", "content": "Assistant Response"}

        MockedAltAI().send.side_effect = side_effect_fn
        events = ["test_event1"]
        system_message = MessageNode(
            role=Role.system, message_content="test_system_message_content")
        driver_wrapper_gen = driver_wrapper(
            events, system_message, AIDriver(MockedAltAI()))
        event_node = next(driver_wrapper_gen)
        self.assertIsInstance(event_node, EventNode)
        self.assertEqual(len(event_node.history), 3)
