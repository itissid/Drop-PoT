from main.prompts.hoboken_girl_prompt import (HOBOKEN_GIRL_SYSTEM_PROMPT,
                                              PARSE_EVENT_PROMPT)


def base_prompt_hoboken_girl(cities, date) -> str:
    return HOBOKEN_GIRL_SYSTEM_PROMPT.format(PLACES=cities, DATE=date)

def default_parse_event_prompt(**kwargs) -> str:
    return PARSE_EVENT_PROMPT.format(**kwargs)