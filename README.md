# poc_drop_content_search
This is a PoC for ingesting text content into a vector database from which we can retrieve relevant search results given a NL Question.

# UPDATE (6th July): Currently debugging some issues in event extraction*. Stay tuned.

# Lay of the land 
## Data Extraction Flow
Always start with the data first and play with it to get a good feel of what it looks like. *THEN* comes the ML/AI play.
```
Scrape and Ingest data -> Post Process Data -> Extract Events*        -> Embedding
     |                        |                    |                        |
  Local File                Local File          SQLLite            SQLLite(or a Vectorstore)
```


1. Code base:
- Core data structure for `Event` is: `main/model/types.py`
- Prompts for extraction are in `main/prompts/hoboken_girl_prompt.py`
- AI and DB utilities are in `main/utils/ai.py` and `main/utils/db.py` along woth other utility functions
-  Main executable is a CLI interface in `main/hoboken_girl_extraction.py`

2. After setting up virtualenv run:
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
## Example command is 
```
python main/hoboken_girl_extraction.py extract-serialize-events 2023-05-23 --cities Hoboken --cities JerseyCity --ingestable-article-file ~/workspace/scraping/examples/postprocessed/hobokengirl_com_hoboken_jersey_city_events_june_23_2023_20230704_170142_postprocessed.txt 

```






