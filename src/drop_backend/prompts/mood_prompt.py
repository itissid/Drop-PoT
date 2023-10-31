def get_system_prompt(
    cities: str, demographics: str = "Millenials and GenZ"
) -> str:
    # This is what I call a "Supervised" One shot learning prompt. I will provide
    # data to control the generation.
    return f"""
You are to generate a list of Human "Moods" and "SubMood" contextual to getting
out and about and doing stuff in your local city from textual event data; I will
shortly provide you the instructions and data for this task.

Here are more specific instructions:

0. I define Mood as primarily a Thought related to what you *want to do*
rather than an emotion that one feels. The thought needs to be such that it triggers a positive or pragmatic
emotional response. For example the Thought of "Going out with Family" can triggers an emotional response
of "Joy", "Wholesomeness", "fulfillment". The Mood(Thought) is morganic, catchy and is
embedded in popular culture of {demographics}, for
example "Lets go Partee!" or "Karaoke night" have a notion of verb/actions but
and they are associated with what "Mood" one is in and hence qualify. Similarly
"Dinner out" or "Brunch" could be considered as a Mood(and a Thought)  but may not
meeting the bar of what qualifies as being a popular culture reference or evoking a prticularly strong emotional 
reaction for some of the {demographics} demographic in {cities}; better it could be "Romantic Outing" or 
"Brunching and Lunching with Friends" instead of "Dinner out" and "Brunch" respectively. 
Use your best judgement to generate moods and submoods and be creative.

1. I will provide you with event data(see complete example below).  Use **ONLY**
this data to generate the Moods and Submoods.

2. The SubMoods are more specific than the encompassing Mood and are also
heirarchically grouped within the Mood.  For example if you infer the event data
to have a general mood: "Quiet Evening", it may have a specific submoods of
"Quiet evenings with friends", "Quiet evening for a stroll".  

3. Every event in the sample must be associated with one or more submood.

4.  Lastly explicitly state why you picked the SubMoods for an event. Add a
REASONING field to each Submood each event text as shown in the Complete example
below.

5. The crowd is young from `{cities}` so its important that the moods and
submoods should be phrased as according to the demographics `{demographics}` and
the jargon they identify with.

6. Make sure **ALL** the events in the input are assigned to at least one submood. In other words 
the mapping from events to submood should be Surjective or Bijective. The events I give you will be 
diverse so they will likely be more than one submood in the result.

7. The output format should be in triple backticks, according to the following complete example:


----------------------
-- Complete example --
----------------------

For example if the data of the events I provide you are the following(in json format):
```
{{
"Event1": "Live music at Maxwell's Tavern in Hoboken",
"Event2": "Groove on Grove in Jersey City",
"Event3": "Art shows at Hoboken Historical Museum",
"Event4": "Visiting Mana Contemporary in Jersey City",
"Event5": "Kids Art Classes at Hoboken Historical Museum Bring your child aged 2-5 for art-making."
"Event6": "Biking on the Hudson River Waterfront Walkway",
"Event7": "Exploring murals in Jersey City",
"Event8": "Kayaking on the Hudson",
"Event9": "Escape Room challenges in Jersey City",
}}
```

Then the plausible moods and submoods expected to be generated (again in json
format template) should be a list as follows:

```
{MOOD_EXAMPLE_OUTPUT}
```



Wait for me to provide you then event data.

"""


MOOD_EXAMPLE_OUTPUT = """
{
    "MOODS":
    [{
        "MOOD": "Urban Adventure",
        "SUB_MOODS": [
            {
                "SUB_MOOD": "City Exploration",
                "DEMOGRAPHICS": ["GenZ", "Millenials"],
                "EVENTS": [
                    "Event6","Event7"
                ],
                "REASONING": "Millenials and Gen Z's curiosity extends to exploring their hometowns of Hoboken and Jersey City. From biking along scenic routes to exploring vibrant street art, there's plenty to discover. "
            },
            {
                "SUB_MOOD": "Thrill-Seeking",
                "DEMOGRAPHICS": ["GenZ"],
                "EVENTS": [
                    "Event8","Event9"
                ],
                "REASONING": "Gen Z seeks adventure and thrills, even within city bounds. Activities like kayaking and escape rooms offer an exciting break from routine. "
            },
        ],
    },
    {
        "MOOD": "Music & Culture",
        "SUB_MOODS": [
            {
                "SUB_MOOD": "Concert Vibes",
                "DEMOGRAPHICS": ["GenZ"],
                "EVENTS": [ "Event1", "Event2" ],
                "REASONING": "Just like their NYC counterparts, Gen Z, Millenials in Hoboken and Jersey City enjoy live music experiences. Local venues and events offer a variety of such opportunities. ",
            },
            {
                "SUB_MOOD": "Cultural Exploration",
                "DEMOGRAPHICS": ["GenZ", "Millenials"],
                "EVENTS": [ "Event3", "Event4" ],
                "REASONING": "Hoboken and Jersey City are rich in culture and arts. Gen Z takes interest in exploring local art scenes and historical places. "
            },
            {
                "SUB_MOOD": "Family Time",
                "DEMOGRAPHICS": ["Millenials"],
                "EVENTS": [ "Event5"],
                "REASONING": "Hoboken and Jersey City are young but also have families. Millenials are more likely to be interested in children events."
            },
        ],
    }
]
}
"""


EVENT_LIST_PROMPT = """
    Process the following (eventid, event) pairs in backticks according to the instructions provided previously.
    ```
    {event}
    ```
"""


def message_content_formatter(raw_str) -> str:
    return EVENT_LIST_PROMPT.format(event=raw_str)


UNSUPERVISED_PROMPT = """
Give me a comprehensive list of Human "moods" contextual to getting out and
about in your local neighborhood at different times of the day and weekday and
weekends when one has free time. I define Mood as primarily an emotion that one
feels and not necessarily a verb or an action.  

Now though these moods are generally not necessarily verbs/actions unless they
are embedded in the popular culture, for example "Lets go Partee!" or "Karaoke
night" have a notion of verb/actions but they are also associated with what
"Mood" one is in.  I want you to pick only the most discriminative examples here
for example "Dinner out" or "Brunch" could be be considered as being "in a  mood
for" for but are not meeting my definition of emotion.

1. I want you to give me these moods, but also as many sub categories of those moods as possible for example :

"Quiet Evening" can be divided into "Quiet evenings with friends", "Quiet
evening for a stroll" etc.  The format should be `"<Mood>" : ["<SubMood1>",
..."<SubMoodN>"]`

Ideally the things you want also enrich our moods, but we can't always find that
in the City. But for each Mood/SubMood I want you to make up as many types of
Place categories in a City and Events happening there that people might
associate them with. Keep it general for example "Quiet evenings with friends"
can be done as a "Game night at Home" or "Book reading club"  and "Quiet evening
for a stroll" could be done "Walk In the park" or "Walking on the waterfront".
"Wicked Fun" can be associated with "Going to a bar",  "Escape room".  Again the
format is:
`<Mood>: [<Place/Activity1>, ....<Place/Activity N>]`

Lastly for each Mood I want you to try and tell me some why do you think its a
mood in popular culture. Quote some references or web links to corroborate.
"""
