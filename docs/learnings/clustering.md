
1. Use KMeans to cluster the embedding of each event from parsed_events.

    The embedding is pregenerated from the utility i have.
    - I need to unify the bases to do alembic migration to add embedding "field" column.
    This will give you a cluster label(integer) for each cluster.
    Do [4, 10] clusters for the items in the dataset. 

2. Once I have all the clusters I can use tSNE to visualize the clusters.
    Does Plotting them in tSNE should tell you which 
    ones are well separated(see plot https://github.com/openai/openai-cookbook/blob/main/examples/Clustering.ipynb)? 

3. Sample docs from each cluster and generate the Submoods and moods using the following prompt.

4. An api that given a location 
    - Retrieve all the events happening around the location you provide. Add distance to each event.

    - A query to retrieve the events that are:
        Now(<= 1 hour): Time upper bound ones + ongoing. Sorted by distance.
        Later(> 1hour): Time lower bound ones + ongoing. Sorted by distance.

prompt = 
f"""
You are to generate a list of Human "Moods" and "SubMood" contextual to getting out and
about and doing stuff in your local neighborhood from textual event data; I will shortly provide you the data for times of the weekday and weekend for this task.

Here are more specific instructions you are to follow for generating moods and submoods:

0. I define Mood as primarily an "emotional" need/state that one feels and not necessarily a verb or an action. It is more organic, catchy and is embedded in popular culture.
1. In the data that I will provide there will be a sample of events from a "cluster" of events that are "similar" and generated using {algorithm_name} algo.  Use ONLY this data to generate the Moods and Submoods.

2. The SubMoods are more specific than the encompassing Mood and are also heirarchically grouped within the Mood.
For example if the event data is inferred to have a general mood of "Quiet Evening" it may have
individual events that can be fall into submoods of "Quiet evenings with friends", "Quiet
evening for a stroll" etc.  

3. Every event in the sample must be associated with a submood.

4. Look at the city where these events are happening and generate the moods and submoods names
based on what will appeal to all demographics in that city. 

5.  Lastly for each Mood I want you to try and tell me some why do you think its
a mood in popular culture of the city. Add a REASONING field to each Submood each event text in the data about why you attached the submood to that event.

6. Now though these moods are generally not necessarily verbs/actions unless
they are embedded in the popular culture, for example "Lets go Partee!" or
"Karaoke night" have a notion of verb/actions but they are also associated with
what "Mood" one is in and hence qualify. Similarly "Dinner out" or "Brunch"
could be considered as being "in a  mood for" for but are not meeting my bar of
what qualifies as emotional state. Use your judgement. Since they are from a cluster
there will likely be only one Mood and a few Submoods for the data I provide.

7. The output format should be in triple backticks:

```
{"MOOD": "<Generated_Mood>", 
    "SUB_MOODS":  [
        {"SUB_MOOD": <Generated_SubMood1>, "EVENTS": ["<Event1>", "<Event15>", ....], "REASONING":"..."},
        {"SUB_MOOD": <Generated_SubMood2>, "EVENTS": ["<Event6>", "<Event3>", ....], "REASONING":"..."},
    ]
} 
```
8. The crowd is young and from {city_name} so the moods and submoods should be
named as such Millenials and Gen Z.

----------------------
-- Complete example --
----------------------

For example if the sample of events I provide you are:
```
{
"Event1": "Live music at Maxwell's Tavern in Hoboken",
"Event2": "Groove on Grove in Jersey City",
"Event3": "Art shows at Hoboken Historical Museum",
"Event4": "Visiting Mana Contemporary in Jersey City"
}
```

Then the moods and submoods you could generate per the formatting template are:

```
[{
        "MOOD": "Music & Culture",
        "SUB_MOODS": [
            {
                "SUB_MOOD": "Concert Vibes",
                "EVENTS": [ "Event1", "Event2" ],
                "REASONING": "Just like their NYC counterparts, Gen Z in Hoboken and Jersey City enjoy live music experiences. Local venues and events offer a variety of such opportunities. ",
            },
            {
                "SUB_MOOD": "Cultural Exploration",
                "EVENTS": [ "Event3", "Event4" ],
                "REASONING": "Hoboken and Jersey City are rich in culture and arts. Gen Z takes interest in exploring local art scenes and historical places. ",
            },
        ],
    }
]
```
------------------

WAIT for me to paste in a set of events and then generate the moods and submoods for them.
Follow the above instructions.
"""


TODO: Decide the right number of clusters vs not having too little in each.

Question we ask ourselves: Why are the clusterings needed if we are going to have to ask ChatGPT
take events and label them with submoods?
Answer: It might be cheaper to just generate one mood from top K per events cluster and add all the remaining events to them.

Question: Can I use KMeans to "score" a new document and assign a submood?
Answer: This could save resources of having to call OpenAI on every event.