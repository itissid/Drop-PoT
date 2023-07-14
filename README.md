# poc_drop_content_search
The idea is to use this framework as a test bed for testing drop's prompt's data quality(for now textual prompts).
Lots of pieces are still missing; The examples in this PoC are not the final prompts, In the real app there will be a BFF(Conversational ChatGPT like api) that will intercept the data and actually polish/filter and serve the prompts.

Tech wise the PoC is ingesting text content into a vector database from which we can retrieve relevant search results(i.e. the bread and butter of prompts) given a NL Query which we call a "[mood](./main/model/mood_seed.py)" which we will infer or generate(seed). 

There are a few core ideas of  I wanted to demonstrate
1. To an extent we can extract structured information from content using OpenAI GPT. For example the `event_json`:
![s](./docs/StructuredInfoFromText.png) column is retrieved from unstructured text using a prompt.

2. Generate seed moods for a locality(Hoboken or South Bangalore) to start off.

3. We can use embeddings from OpenAI API to emnde data from steps 1, 2 (see the embeddings table in drop.db) the purpose is to find similarity 
in a dataset using FAISS [Vector search](https://datasette.io/plugins/datasette-faiss):
![relevant events](./docs/Relevant%20Events.png). There is nothing new about embeddings and vector databases. What is new is we *dynamically index* a subset of the data and query it repeatedly using 
datasett-faiss. At scale we can do this using faiss. The need for dynamic index comes from  the so called "filter query", which I imagine can come from user cues  from our Shared space or from the Context

3. TODO: We can order the events in a reverse spatial-cronological order.
4. TODO: Lead into how we can go from issues we Cold start towards improving the quality of content retrieved using
a ML NLP model.

# UPDATE (14th July): 
Play with the database 
The database [dump](https://www.dropbox.com/home/project_drop) from tg using datasette:
Install [datasette](https://datasette.io/) in the python virtual env and just say `datasette drop.db`.
This is what you should see is ![this](./docs/Screenshot%202023-07-14%20at%207.01.44%20AM.png):

## How to retrieve similar documents?
The 

# Lay of the land 
## Data Extraction Flow
Always start with the data first and play with it to get a good feel of what it looks like. *THEN* comes the ML/AI play.
```
Scrape and Ingest data -> Post Process Data -> Extract Events*        -> Embedding
     |                        |                    |                        |
  Local File                Local File          SQLLite            SQLLite(or a Vectorstore)
```


## Code base layout:
- Core data structure for `Event` is: `main/model/types.py`
- Prompts for extraction are in `main/prompts/hoboken_girl_prompt.py`
- AI and DB utilities are in `main/utils/ai.py` and `main/utils/db.py` along woth other utility functions
-  Main executable is a CLI interface in `main/hoboken_girl_extraction.py`

## After setting up virtualenv/pyenv you can
Run:
`python main/hoboken_girl_extraction.py --help`
You will see three commands that are explained in the flow above.
```
╭─ Commands ──────────────────────────────────────────────────────────────────────────────────────────────╮
│ extract-serialize-events                            Call parse_events and get                           │
│ ingest-urls                                                                                             │
│ post-process                                                                                            │
╰───────────────
```

# What each step of the Flow does.

# 1. Ingest URLs will scrape hoboken girl web page:
Potentially other web page that has content, but script might need tuning.
## Example command:
```
python main/hoboken_girl_extraction.py ingest-urls /Users/sid/workspace/scraping/examples/ https://www.hobokengirl.com/hoboken-jersey-city-events-june-30-2023/ https://www.hobokengirl.com/hoboken-jersey-city-events-june-23-2023/ --run-prefix test
```
will scrape two pages(internally using BeautifulSoup and requests)

# 2. Post Process command: 
Specific to hoboken girl only, it delimits each event using some heuristic pattern recognition i.e. it places the `$$$` delimiter between events to consume them one at a time for next step in the flow(see [this](https://github.com/itissid/poc_drop_content_search/blob/be022ad969598ec768a7d8836f9bc8131325d1aa/examples/postprocessed/hobokengirl_com_hoboken_jersey_city_events_june_23_2023_20230704_170142_postprocessed.txt) file)
Since its heuristic one need to double check if all events have been identified(~90% of the events from HG are processed fine)
## Example command :
```
>> python main/hoboken_girl_extraction.py post-process  ~/workspace/scraping/examples/test_ingestion/hobokengirl_com_hoboken_jersey_city_events_june_30_2023_20230704_170142.txt
```

# 3. Extract Events(Use AI!)
> YOU WILL NEED AN OPEN AI KEY.  https://openai.com/pricing

WIP: See updates on July 6th but the idea is to create Event objects per the prompt instruction to index into the SQLite index.
## Example command is :
```
python main/hoboken_girl_extraction.py extract-serialize-events 2023-05-23 --cities Hoboken --cities JerseyCity --ingestable-article-file ~/workspace/scraping/examples/postprocessed/hobokengirl_com_hoboken_jersey_city_events_june_23_2023_20230704_170142_postprocessed.txt 
```

There will be errors in this process due to OpenAI timing out. In running this I
found that this errored in 2-3/100 data points, even with 10 retries and
exponentail back off. YMMV. But we need to eventually deal with this.  A dumb
way is to keep retrying forever but that might take a long time for more than a
few 1000 examples. A more clever way is to use async frameworks like celery and
AMPQ to deal with the failures in a more clever way. 

We record the failures in the database:

|description|event_json|truncated_event_raw_text                            |failure_reason                                                                                                                                                                                                                                                                         |truncated_filename|version|
|-----------|----------|----------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------|-------|
|           |null      |Pride Run at Pier A Park   Saturday, June 24th &#124; ...|("Connection broken: InvalidChunkLength(got length b'', 0 bytes read)", InvalidChunkLength(got length b'', 0 bytes read))                                                                                                                                                              |hobokengi...      |v1     |
|           |null      |Marisa Monte at NJPAC   Friday, June 23rd    &#124; 8P...|("Connection broken: InvalidChunkLength(got length b'', 0 bytes read)", InvalidChunkLength(got length b'', 0 bytes read))                                                                                                                                                              |hobokengi...      |v1     |
|           |null      |Musical Cooking Class by One Great Vegan   Saturd...|That model is currently overloaded with other requests. You can retry your request, or contact us through our help center at help.openai.com if the error persists. (Please include the request ID f9414e90d044c6edf5b33ce1bcc5115c in your message.) (Error occurred while streaming.)|hobokengi...      |v1     |
|           |null      |State Fair Meadowlands at MetLife Stadium   Ongoi...|That model is currently overloaded with other requests. You can retry your request, or contact us through our help center at help.openai.com if the error persists. (Please include the request ID 69490a87a9700a07a206ca1900d0d305 in your message.) (Error occurred while streaming.)|hobokengi...      |v1     |
|           |null      |The Laugh Tour Comedy Club at Dorrian’s Red Hand ...|                                                                                                                                                                                                                                                                                       |hobokengi...      |v1     |


# 4. Use OpenAI Embeddings to create Embedding vectors
1. To create the embeddings for the moods in mood_seed.py use. Example: 
```
python main/hoboken_girl_extraction.py index-moods MILLENIALS
```
This creates a table called MoodJsonTable. 

TODO: More to come in next commit




