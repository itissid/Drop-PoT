# What's in here?

This is a framework, tools, libs that enables my demo. Think workflow automation for ingesting content like [vellum.ai](vellum.ai) and you will get a picture(except that i did not know about vellum and this integrates only with OpenAI for my use case :) ). See [demo](https://github.com/itissid/drop_webdemo) based on these tools. It has
1. An api(see ai.py) with OpenAI Api to ingest `events`(things that have attributes like date, time, address, pricing what have you) and extract structured data from it.
2. There is a nifty little library that can help you generate stubs for the function call API for OpenAI. Given a Pydantic data model inheriting from the [BaseClass](https://github.com/itissid/poc_drop_content_search/blob/b771ef7a96b091f98b554b8697a22a89fb346226/src/drop_backend/types/base.py#L4) it can:
  - Genenrate [code](https://github.com/itissid/Drop-PoT/blob/c982edda666fbf047db193f2b24a77dd6b2fa7a5/tests/integration/fixtures/schema/weather_event_schema.py) for the JsonSchema input to the OpenAI function API and [hooks it up](https://github.com/itissid/Drop-PoT/blob/c982edda666fbf047db193f2b24a77dd6b2fa7a5/src/drop_backend/lib/event_node_manager.py#L105-L124) with your Pydantic Model to [get](https://github.com/itissid/Drop-PoT/blob/c982edda666fbf047db193f2b24a77dd6b2fa7a5/src/drop_backend/lib/event_node_manager.py#L160) the function return value. All you have to do is:
    - 1: Create your base pydantic model like [here](https://github.com/itissid/Drop-PoT/blob/c982edda666fbf047db193f2b24a77dd6b2fa7a5/tests/integration/fixtures/weather_event.py#L23) and implement the function call and return whatever you want. For this project the I did not have to make the actual prescribed returned [AI function call](https://platform.openai.com/docs/api-reference/chat/create#chat-create-function_call), but instead but to [validate](https://github.com/itissid/Drop-PoT/blob/c982edda666fbf047db193f2b24a77dd6b2fa7a5/src/drop_backend/types/city_event.py#L90) the returned data from AI for the `event`, but you can call whatever function you want in the hooks provided.
    - 2: Once created you can wire it up as shown [here](https://github.com/itissid/poc_drop_content_search/blob/124d380e21439cf4f3f90ca617581bd774913dd8/tests/integration/test_message_to_api.py#L110) in the unit test to create an EventManager instance and pass it to the main [driver_wrapper](https://github.com/itissid/poc_drop_content_search/blob/b771ef7a96b091f98b554b8697a22a89fb346226/src/drop_backend/lib/ai.py#L140) instance that drives the AI.
    - 3: To improve your System prompts iteratively; there is an API called [InterrogativeProtocol](https://github.com/itissid/Drop-PoT/blob/main/src/drop_backend/lib/interrogation.py#L22). Think of it analogus to using `pdb` to introspect the code and fix it. Instead here you can interact with the AI like a chat if your initial prompt produced.
  - I dogfooded this library in my code and used many example stubs in the code, this one was for tests:
  ```
  Example for creating WeatherEvent base class and hook it to AI.
  
   PYTHONPATH=".:src/:tests/" python -m drop_backend.commands config-generator-commands gen-model-code-bindings WeatherEvent \
   --schema-directory-prefix tests/integration/fixtures/schema/ --type-module-prefix tests.integration.fixtures
  
  # OR if your root python package starts at the root dir of your project, your virtualenv should follow this template:

  python -m  drop_backend.commands config-generator-commands gen-model-code-bindings <CamelCasePydanticClass> \
  --schema-directory-prefix your_base_package/inner_package/schema \
  --type-module-prefix your_base_package.inner_package
  ```
  Just note to create the `WeatherEvent` example pydantic model in the file with the name `weather_event.py`.

  3. Additionally to support NL categorization(a [picture](https://github.com/itissid/drop_webdemo/blob/main/docs/DetailsSmall.jpg) is a 1000 words) of events(kind of like RAG: Use current `event` data only to generate categories) it has utilities to ground AI generated categores by embedding the info in prompts or index the embeddings for events and using vector similarity(K Means) to generate categories. For example for different extracted details of the [events](https://github.com/itissid/poc_drop_content_search/blob/7642f0792c68a104fa5628e4c9663b099c7a1ec4/src/drop_backend/commands/embedding_commands.py#L156) into a SQLite database.
  4. Since `event`s are happening around the city they need to be geocoded, direction and distance needs to be supported. To that extent some utilities exist to use ORS-OpenRouteService to support it.
  5. Use of modern tooling like poetry, pytest, docker to generate wheels for use.


# UPDATE (14th July): 
Play with the database: The database [dump](https://www.dropbox.com/home/project_drop) can be visualized using datasette:

Install [datasette](https://datasette.io/) in the python virtual env and just say `datasette drop.db`.

This is what you should see: ![this](./docs/Screenshot%202023-07-14%20at%207.01.44%20AM.png)



# Data Extraction Flow
Always start with the data first and play with it to get a good feel of what it looks like. *THEN* comes the ML/AI play. Here are some  important extraction flows:
```
Scrape and Ingest data -> Post Process Data -> Extract Events*        -> Embedding
     |                        |                    |                        |
  Local File                Local File          SQLLite            SQLLite(or a Vectorstore)

 Extracted Event -> Reverse GeoCode
     |                    |
   SQLite              SQLite

 Extracted Event -> Categorization
     |                    |
   SQLite              SQLite
```


## Code base layout:
- Since function calling is so central to the framework, there is a Pydantic Type called [`CreatorBase`](https://github.com/itissid/poc_drop_content_search/blob/b771ef7a96b091f98b554b8697a22a89fb346226/src/drop_backend/types/base.py#L4) that aids in creation of validated types from AI function call responses.
- A wrapper data structure for marshalling internal types to a stream of messages for AI is `Event` in `src/drop_backend/model/ai_conv_types.py`. 
- The `EventManager` that manages function calling: `src/drop_backend/lib/event_node_mananger.py`.
- Prompts for extraction are in `src/drop_backend/prompts/hoboken_girl_prompt.py`.
- AI and DB libs are in `src/drop_backend/lib/ai.py` and `src/drop_backend/lib/db.py`.
- An important executable is a CLI interface in `src/drop_backend/commands/hoboken_girl_extraction.py`. There are many others to reverse geo tag, support RAG based extraction etc in `src/drop_backend/commands/`
- ORS, reverse geotagging, formatting and other useful things are in `src/drop_backend/utils/`.

## After setting up virtualenv/pyenv you can
Run:
`poetry run python -m  drop_backend.commands --help`
You will see three commands that are explained in the flow above.
```
╭─ Commands ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ config-generator-commands                  Generate Code for validating AI responses                                                                                                                                              │
│ data-ingestion-commands                    Groud Events and Generate Categories for them                                                                                                                                                                                                  │
│ reverse-geocoding-commands                                                                                                                                                                                                                                                                │
│ webdemo-adhoc-commands                                                                                                                                                                                                                                                                    │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
poetry run python -m  drop_backend.hoboken_girl_extraction --help

```
╭─ Commands ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ demo-retrieval                                                                                                                                                                                                                                                                            │
│ extract-serialize-events                      Call AI to parse all teh events in ingestable_article_file to extract structured events and then save them to the database as JSON.                                                                                                         │
│ index-event-embeddings                        Retrieve the embeddings for the events and add them to a SQLite vector store                                                                                                                                                                │
│ index-mood-embeddings                         Used for Indexing Categories as embeddings.                                                                                                                                                                                                 │
│ index-moods                                   Generated and index the moods using a general prompt, no Grounding.                                                                                                                                                                         │
│ ingest-urls                                   Take a URL and extract page text from it                                                                                                                                                                                                    │
│ post-process                                  Custom code to split web text to individual events, reduces the work for ingestion,(for Hoboken Girl Event Pages only)                                                                                                                      │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

```

# What each step of the Flow does.

# 1. Ingest URLs will scrape hoboken girl web page:
Potentially other web page that has content, but script might need tuning.
## Example command:
```
python -m drop_backend.commands.hoboken_girl_extraction \
ingest-urls ~/workspace/scraping/examples/ https://www.hobokengirl.com/hoboken-jersey-city-events-june-30-2023/ https://www.hobokengirl.com/hoboken-jersey-city-events-june-23-2023/ --run-prefix test
```
will scrape two pages(internally using BeautifulSoup and requests)

# 2. Post Process command: 
We feed the events from scraped text into GPT API one by one so we need to put a delimiter between events in the text. This is Specific to hoboken girl data where all events are in one file and I need to separate them. The step is simple it delimits each event  using some heuristic pattern recognition i.e. it places the `$$$` delimiter between events to consume them one at a time for next step in the flow(see [this](https://github.com/itissid/poc_drop_content_search/blob/be022ad969598ec768a7d8836f9bc8131325d1aa/examples/postprocessed/hobokengirl_com_hoboken_jersey_city_events_june_23_2023_20230704_170142_postprocessed.txt) file)
Since its heuristic one need to double check if all events have been delimited(~90% of the events from HG are processed fine). It makes athe manual correction that the pattern made much easier. 

## Example command :
```
>> python -m drop_backend.commands.hoboken_girl_extraction.py post-process  ~/workspace/drop/examples/test_ingestion/hobokengirl_com_hoboken_jersey_city_events_june_30_2023_20230704_170142.txt
```

# 3. Extract Events(Use AI!)
> YOU WILL NEED AN OPEN AI KEY.  https://openai.com/pricing

## Example command is :
```
poetry run python -m  main.hoboken_girl_extraction extract-serialize-events 2023-05-23 --cities Hoboken --cities JerseyCity --cities NewYorkCity --ingestable-article-file ~/workspace/drop/examples/postprocessed/hobokengirl_com_hoboken_jersey_city_events_september_1_2023_20230913_160012_a.txt_postprocessed
```

There will be errors in this process due to OpenAI timing out. In running this I
found that this errored in 2-3/100 data points, even with 10 retries and
exponentail back off. YMMV. But we need to eventually deal with the errors in data.  A dumb
way to do this is to keep retrying forever but that might take a long time for more than a
few 1000 examples. A more clever way is to use async frameworks like celery and
AMPQ to deal with the failures by queing them onto a retry queue and process them later. 

We record the failures in the database:

|description|event_json|truncated_event_raw_text                            |failure_reason                                                                                                                                                                                                                                                                         |truncated_filename|version|
|-----------|----------|----------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------|-------|
|           |null      |Pride Run at Pier A Park   Saturday, June 24th &#124; ...|("Connection broken: InvalidChunkLength(got length b'', 0 bytes read)", InvalidChunkLength(got length b'', 0 bytes read))                                                                                                                                                              |hobokengi...      |v1     |
|           |null      |Marisa Monte at NJPAC   Friday, June 23rd    &#124; 8P...|("Connection broken: InvalidChunkLength(got length b'', 0 bytes read)", InvalidChunkLength(got length b'', 0 bytes read))                                                                                                                                                              |hobokengi...      |v1     |
|           |null      |Musical Cooking Class by One Great Vegan   Saturd...|That model is currently overloaded with other requests. You can retry your request, or contact us through our help center at help.openai.com if the error persists. (Please include the request ID f9414e90d044c6edf5b33ce1bcc5115c in your message.) (Error occurred while streaming.)|hobokengi...      |v1     |
|           |null      |State Fair Meadowlands at MetLife Stadium   Ongoi...|That model is currently overloaded with other requests. You can retry your request, or contact us through our help center at help.openai.com if the error persists. (Please include the request ID 69490a87a9700a07a206ca1900d0d305 in your message.) (Error occurred while streaming.)|hobokengi...      |v1     |
|           |null      |The Laugh Tour Comedy Club at Dorrian’s Red Hand ...|                                                                                                                                                                                                                                                                                       |hobokengi...      |v1     |

# 3.1 Generate the moods(without RAG)
This step is extremely hackish. We want to be able to use moods from the shared space that can retrieve relevant things for the user to see. The idea is encapsulated in the [PROMPT](./main/model/mood_seed.py)
variable where I gave it to ChatGPT to just generate moods for me. 

This is far from perfect since it results Missing or Overlapping data between moods. With our small dataset 
I have faced more of the Missing data than the overlapping issue. 


Poor score with moods(due to lack of data):
![moods](./docs/MoodsWithLackOfDataForThem.png)

# 3.2 Generate the moods(with RAG and preferred)
To generate grounded moods use the following command:
```
 python -m drop_backend.commands data-ingestion-commands index-event-moods --cities="Hoboken,JerseyCity" --demographics="Millenials,IndianAmericans,GenZ" hobokengirl_com_diwali_events_hudson_county_2023_20231110_065438_postprocessed v1
 ```
 The results are much better than using kmeans on vector emebedding and then using the top docs to get the moods.

TODO: My RAG is pretty simple, feed the actual event with the prompts and generate the mood

# 4. Reverse Geocode the events
- First run the ORS service that can do reverse geocoding
Assuming you have done some of the steps in [how_to_nominatim](./docs/learnings/how_to_nominatim.md) doc, you can run the docker image like so:
```
 docker run -it -e \
 PBF_PATH=/osm-maps/data/new-york_new-york.osm.pbf \
 -p 8080:8080  \
 -v /Users/sid/workspace/drop/geodata/new-york_new-york.osm.pbf:/osm-maps/data/new-york_new-york.osm.pbf \
 --name sid-nomatim2 \   
 mediagis/nominatim:4.2
```

- Once its up and running:
```
 python -m drop_backend.commands reverse-geocoding-commands  do-rcode hobokengirl_com_hoboken_jersey_city_events_november_10_2023_20231110_065435_postprocessed  v1
```
can do the reverse geocoding.

> At this point we are almost ready to run the web service
with the data in drop DB. DO a final test using the command:

```
poetry run python  -m drop_backend.commands  webdemo-adhoc-commands --loglevel debug geotag-moodtag-events --help # hobokengirl_com_hoboken_jersey_city_events_september_1_2023_20230913_160012_a.txt_postprocessed v1 40.741924698522084 ' -74.0358352661133' --when now --now-window-hours 1 --stubbed-now 2023-11-09
```
which tests the routine that gathers all the data for displaying on the webpage.

# 5(Optional). Use OpenAI Embeddings to create Embedding vectors
1. To create the embeddings for the moods in mood_seed.py use. Example: 
```
python main/hoboken_girl_extraction.py index-moods MILLENIALS
```
This creates a table called MoodJsonTable. 

Next we create embeddings for the moods.
```
python main/hoboken_girl_extraction.py index-mood-embeddings MILLENIALS
```

# 5. Demo!
## New Demo(October 2023)
[UPDATE: 10th Nov 2023] See demo here: http://drophere.co

## OLD Demo
https://github.com/itissid/drop_webdemo

Lets use the mood embeddings to find relevant embeddings. Check out [this](./example_retrieval.sql) script.
You should run it in the datasette browser after you have installed the plugin in your env.
Here are some of the results. Rule of thumb: below 0.36 distance the results are better:
![moods](./docs/MoodsThatHaveSufficientData.png)






