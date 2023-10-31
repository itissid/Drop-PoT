# pylint: skip-file
# mypy: ignore-errors
# @pylance-disable=all
class BasicInteraction:
    """
    Format the messages to and from the AI.
    It will
    """

    def __init__(self, ai: AI):
        self._ai = ai


class HumanInLoopInteraction:
    """A wrapper around the AI class that allows a human to interact with the AI.
    so as to fix a response from it in the loop.

    In addition to the initial System Prompt and the User's Prompt when a user interacts with the AI to fix its
    mistakes, the AI then takes this new instruction into account for the next task we give it.
    """

    def __init__(self, ai: AI):
        self._ai = ai
        self._autopilot = False
        self._internally_started = False

    def _internal_start(self, partial_event_node: EventNode) -> None:
        if self._internally_started:
            return
        assert partial_event_node.system_prompt is not None
        assert (
            partial_event_node.conversation_messages is not None
            and len(partial_event_node.conversation_messages) == 1
        ), "The interrogation messages must be initialized with the user's prompt."

        prev_user_message = partial_event_node.conversation_messages[-1]
        assert prev_user_message.role == Role.user
        messages = self._ai.start(
            partial_event_node.system_prompt,
            prev_user_message.message_content.format(
                **prev_user_message.template_vars
                if prev_user_message.template_vars
                else {}
            ),
        )
        assert len(messages) == 3

        ai_reply = messages[-1]
        partial_event_node.conversation_messages.append(
            MessageNode(
                role=Role.assistant,
                id=ai_reply.id,
                message_content=ai_reply["content"],
                message_function_call=ai_reply["function_call"],
            )
        )

        self._internally_started = True

    def process_event(self, partial_event_node: EventNode):
        # Pass through to AI.next unless human in loop is enabled.

        if not self._internally_started:
            self._internal_start(partial_event_node)
        else:
            prev_user_message = partial_event_node.conversation_messages[-1]
            assert prev_user_message.role == Role.user
            _messages = self._ai.next(
                partial_event_node.to_open_ai_api_messages(),
                function=prev_user_message.message_function_call,
                explicitly_call=prev_user_message.explicit_fn_call,
            )
            partial_event_node.conversation_messages.append(
                MessageNode(
                    role=Role.assistant,
                    id=time_uuid.TimeUUID(),  # TODO: FIX ME
                    message_content=_messages[-1]["content"],
                    message_function_call=_messages[-1]["function_call"],
                )
            )
        # TODO: Once interrogation is done we should have a final message that
        # summarizes the interrogation and we should be appended to the system
        # prompt. The user must be responsible to empty the interrogation messages.
        should_amend = self._ask_user_should_ai_amend()
        if should_amend:
            while should_amend:
                assert self._interrogation is not None
                partial_event_node.conversation_messages.append(
                    MessageNode(
                        role=Role.user,
                        id=time_uuid.TimeUUID(),  # FIX ME
                        message_content=self._interrogation,
                        metadata={"is_interrogation": True},
                    )
                )
                _messages = self._ai.next(
                    partial_event_node.to_open_ai_api_messages(),
                    function=prev_user_message.message_function_call,
                    explicitly_call=prev_user_message.explicit_fn_call,
                )
                partial_event_node.conversation_messages.append(
                    MessageNode(
                        role=Role.assistant,
                        id=time_uuid.TimeUUID(),  # FIX ME
                        message_content=_messages[-1]["content"],
                        message_function_call=_messages[-1]["function_call"],
                        metadata={"is_interrogation": True},
                    )
                )
                should_amend = self._ask_user_should_ai_amend()
            # TODO: Add a final message that summarizes the interrogation and should ideally be appended to the
            # system prompt
            # TEST: Send in a message one by one and check
            # 1. The interrogation messages are in the EventNode
            # 2. The summarization of interrogation is good and included in the event node
            # 3. One the callee side they need to empty all interrogation messages and only retain the summarization.
        else:
            #
            pass

        pass

    def _ask_user_should_ai_amend(
        self,
        override_prompt: str = "Would you like to interact with Assistant to amend its response (yes/no/never)",
        choices=("yes", "no", "never"),
        default="never",
    ) -> bool:
        """
        Ask a user if they want to amend the response of the AI.
        """
        self._interrogation = None

        if self._autopilot:
            return False

        should_amend = (
            get_user_option(override_prompt, choices, default) == "yes"
        )

        if should_amend == "never":
            self._autopilot = True
            return False

        if should_amend is True:
            while not self._interrogation:
                self._interrogation = typer.prompt(
                    _optionally_format_colorama(
                        "Now, tell assistant what you want to fix: ",
                        True,
                        Fore.RED,
                    )
                )

        return should_amend

    # TODO(Sid): Return an object instead of messages with fields set.
    def amend(self, messages: List[dict[str, str]]):
        # TODO: Add all interrogation messages to the chat context.
        assert (
            self._interrogation
        ), "Interrogation must be set before calling amend()"

        logger.info(
            _optionally_format_colorama("AI: ", True, Fore.GREEN)
            + "".join(chat)
        )
        logger.info(
            f"{_optionally_format_colorama('Function call: ', True, Fore.GREEN)}: {json.dumps(func_call)}"
        )
        conversation_messages = messages.copy()

        # TODO Save all the interrogation messages.
        while self._ask_user_should_ai_amend():
            conversation_messages = self.human_in_loop.amend(
                conversation_messages
            )

            response = _try_completion(
                conversation_messages,
                self.model,
                function=function,
                temperature=self.temperature,
                explicitly_call=explicitly_call,
            )
            chat, func_call = _chat_function_call_from_response(response)
            conversation_messages += [
                {
                    "role": "assistant",
                    "content": "".join(chat),
                    "function_call": json.dumps(func_call),
                }
            ]
            logger.info(
                _optionally_format_colorama("Assistant: ", True, Fore.GREEN)
                + "".join(chat)
            )
            if func_call["name"] is not None:
                logger.info(
                    f"{_optionally_format_colorama('Function call:', True, Fore.GREEN)}: {json.dumps(func_call)}"
                )

        return messages + [
            {
                "role": "user",
                "content": self._interrogation,
            }
        ]

    def post_amend(self):
        # TODO: Call edit_dict() to fix a response manually.
        pass

        sautopilot = False

    for i, event in enumerate(events):
        # 2. Send the remaining prompts
        try:
            event_obj = _parse_raw_event(ai, messages[:1], event)
            if not event_obj:
                # TODO: Log this in SQL as an error in processing as NoEventFound.
                engine = ctx.obj["engine"]
                add_event(
                    engine,
                    event=None,
                    original_text=event,
                    failure_reason="NoEventFunctionCallByAI",
                    filename=ingestable_article_file.name,
                    version=version,
                )
                continue
            if not autopilot:
                typer.echo("Confirm is the event looks correct or edit it")
                typer.echo(
                    f"{_optionally_format_colorama('Raw Event text', True, Fore.GREEN)}'\n'{event}"
                )
                edit_dict(asdict(event_obj))
                # The user may want to turn on autopilot after a few events.
                if go_autopilot():
                    typer.echo(
                        "Autopilot is on. Processing all events without human intervention."
                    )
                    autopilot = True
            else:
                typer.echo(
                    f"Autopilot is on. Processing  event {_optionally_format_colorama(str(i+1), True, Fore.GREEN)} without human intervention."
                )
            engine = ctx.obj["engine"]
            if event_obj.name not in element_names_already_seen:
                add_event(
                    engine,
                    event=event_obj,
                    original_text=event,
                    failure_reason=None,
                    filename=ingestable_article_file.name,
                    version=version,
                )
            else:
                logger.debug(
                    f"Skipping {i}th event with name {event_obj.name} as it was already seen."
                )
        except Exception as e:
            engine = ctx.obj["engine"]
            id = add_event(
                engine,
                event=None,
                original_text=event,
                failure_reason=str(e),
                filename=ingestable_article_file.name,
                version=version,
            )
            logger.error(f"Error processing event {id}")
            logger.exception(e)
            if num_errors > max_acceptable_errors:
                typer.echo(
                    f"Too many errors. Stopping processing. Please fix the errors and run the command again."
                )
                return
            num_errors += 1
            continue
    logger.info(f"Done processing all events with {num_errors} errors.")


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

    def start(
        self, system: str, user: str, functions=None, explicitly_call=False
    ):
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        return self.next(
            messages, functions=functions, explicitly_call=explicitly_call
        )

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
        functions=None,
        explicitly_call=False,
    ):
        response = self._try_completion(
            messages, functions=functions, explicitly_call=explicitly_call
        )
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

    def _try_completion(self, messages, functions=None, explicitly_call=False):
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
                    function_call=None
                    if not explicitly_call
                    else {"name": function["name"]},
                    temperature=self.temperature,
                )
        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            raise e
        return response
