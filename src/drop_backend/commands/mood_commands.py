import json
import logging
import math
from typing import cast

import typer
from pydantic import ValidationError
from sqlalchemy import column

from ..lib.ai import AIDriver, AltAI, driver_wrapper
from ..lib.event_node_manager import EventManager
from ..lib.interrogation import InteractiveInterrogationProtocol
from ..model.ai_conv_types import MessageNode, Role
from ..model.mood_model_supervised import (
    handle_mood_submood,
    handle_sub_mood_event,
)
from ..model.persistence_model import get_parsed_events
from ..prompts.mood_prompt import get_system_prompt, message_content_formatter
from ..types.mood_submood import MoodSubmood

logger = logging.getLogger(__name__)


def generate_and_index_event_moods(
    ctx: typer.Context,
    filename: str,
    version: str,
    cities: str,  # CSV list
    demographics: str,  # CSV list
    batch_size: int,
):
    # Get all teh events from parsed_events by filename and version.
    events = get_parsed_events(
        ctx,
        filename=filename,
        version=version,
        columns=[column("id"), column("name"), column("description")],
    )
    system_message = MessageNode(
        role=Role.system,
        message_content=get_system_prompt(
            cities=cities, demographics=demographics
        ),
    )
    raw_event_batches = [
        json.dumps({
            "Event" + str(event.id): event.name + ".\n " + event.description
            for event in events[batch_size * batch_num: batch_size*(batch_num+1) ]
        })
        for batch_num in range(0, math.ceil(len(events) / batch_size))
    ]
    # Generate json using AI
    event_manager = EventManager(
        "MoodSubmood", "drop_backend.types", "drop_backend.types.schema"
    )
    ai_driver = AIDriver(AltAI(), event_manager=event_manager)
    # Limit me to test.
    # batch_event = json.dumps(raw_events, indent=2)
    # print(f"Num events = {len(raw_events)}")
    interrogation_protocol = InteractiveInterrogationProtocol()
    driver = driver_wrapper(
        raw_event_batches,
        system_message=system_message,
        ai_driver=ai_driver,
        user_message_prompt_fn=lambda event: message_content_formatter(
            event.raw_event_str
        ),
        event_manager=event_manager,
        interrogation_protocol=interrogation_protocol,
    )
    for _, (event, error) in enumerate(driver):
        if error:
            assert isinstance(error, ValidationError), (
                "Only validation error expected to be handled. You may want to add more "
                "error handling here."
            )
            assert event.history is not None
            logger.error(
                "Failed to generate mood submood for event %s",
                event.raw_event_str,
            )
            continue

        # Parse the JSON
        event_obj = cast(MoodSubmood, event.event_obj)
        moods = event_obj.MOODS
        for mood in moods:
            submoods = mood.SUB_MOODS
            for submood_dict in submoods:
                submood = submood_dict.SUB_MOOD
                mood_sub_mood_entry = handle_mood_submood(
                    ctx, mood.MOOD, submood
                )
                handle_sub_mood_event(ctx, submood_dict, mood_sub_mood_entry)
