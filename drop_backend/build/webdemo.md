I am a software engineer. I have put together a webdemo with mobile friendly properties. I have used bootstrap css, python(fast API). I need to complete it. Here is what I have already(after that I will explain what I need): 

The routes for the api I have already written are summarized as follows in a app/main.py:
```
class When(str, enum.Enum):
    NOW = "now"
    LATER = "later"

@app.get("/presence/where", response_class=HTMLResponse)
async def where(request: Request):
    """
    Tell us where you are on a map rendered by this route via leaflet.
    """
    ...

@app.get("/presence/are_you_really_here", response_class=HTMLResponse)
async def validate(lat: float = None, long: float = None):
    if _is_where_you_are_valid(lat, long):
        return "Ok"
    raise HTTPException(
        status_code=400,
        detail="The selected location is not valid or outside the allowed area.",
    )


@app.get("/presence/here/", response_class=HTMLResponse)
async def here(
    request: Request,
    lat: Optional[float] = None,
    long: Optional[float] = None,
    when: When = When.NOW,
):
    """
    Validate the location(which establishes you "here"). Here being in a certain predefined area.
    If the location is valid then return the events using swiper UI
    """
    # If location is validated. The data will be rendered in swipers here. 
        if lat is not None and long is not None:
        print("Lat long passed by user")
        request.session["lat"] = lat
        request.session["lng"] = long

    lat = request.session.get("lat")
    long = request.session.get("lng")
    print("Lat long from session", lat, long)

    if _is_where_you_are_valid(lat, long):
        print("You are here.")
        # now lets get all the events that are going to happen close to now
        datetime_now = datetime.strptime("2023-09-01", "%Y-%m-%d")
        # TODO: call geotag_moodtag_events then group them by submood and then by when and if there are events load them into respective swipers. Otherwise call geotag_moodtag_events with When.LATER and load them

        return templates.TemplateResponse(
            "here_partial.html", {"request": request, "when": when.value}
        )
    raise HTTPException(
        status_code=400,
        detail="The selected location is invalid or outside the allowed area.",
    )

def _is_where_you_are_valid(lat: float, long: float) -> bool:
    ... validation code...
```


The webdemo has two "pages". 
The first will always display a fixed map georgaphy in the center of the web page where a user can drop a pin to suggest where they ought to be. 


The second page has two buttons Now and Later. Each has multiple row of swipers initialized in this template with dummy data for now(using jinja2). This dummy data needs to be replaced as a part of this task(see later instructions). This is the here_partial.html template: 
```
{% extends "here_base.html" %}
{% block head %}
{{ super() }}
{% endblock head %}
{% block content %}
<div class="swiper-container p-3">
    {% for i in range(1, 6) %}
    <div class="swiper {{when}}-{{ loop.index }} row p-1">
        <div class="swiper-wrapper {{when}}">
            {% for j in range(1, 4)%}
            <div class="swiper-slide {{when}}">
                <span>{{ when }} slide {{ j }}</span>

                <!-- Content for each swiper from template variables. -->
            </div>
            {% endfor %}
        </div>
        <!-- Add Pagination -->
        <div class="swiper-button-next {{when}}"></div>
        <div class="swiper-button-prev {{when}}"></div>
    </div>
    {% endfor %}
</div>
<script>
    {% for i in range(1, 6) %}
    const swiper{{ loop.index }} = new Swiper('.swiper.{{when}}-{{loop.index}}', {
        slidesPerView: "auto",
        spaceBetween: 40,
        navigation: {
            nextEl: ".swiper-button-next.{{when}}",
            prevEl: ".swiper-button-prev.{{when}}",
        },
    });
    {% endfor %}
</script>
{% endblock content %}
{% block footer %}
{% endblock footer %}
```
here_base.html template is:
```
<!DOCTYPE html>
<html lang="en">

<head>
    {% block head %}
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, minimum-scale=1, maximum-scale=1" />
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://unpkg.com/swiper/swiper-bundle.min.css" />
    <link rel="stylesheet" href="/static/css/styles.css">
    <script src="https://unpkg.com/swiper@11.0.2/swiper-bundle.min.js"></script>
    <script src="/static/js/scripts.js"></script>
    {% endblock head %}
</head>

<body>
    <div id="content">

        <div class="fixed-bottom d-flex justify-content-center p-3">
            <div class="btn-group" role="group" aria-label="Now and Later buttons">
                <button onclick="beHere('now')"
                    class="btn btn-primary {{ 'active' if when == 'now' else 'inactive'}}">Now</button>
                <button onclick="beHere('later')"
                    class="btn btn-secondary {{ 'inactive' if when == 'now' else 'active' }}">Later</button>
            </div>
        </div>


        {% block content %}{% endblock %}
    </div>
    <div id="footer">
        {% block footer %}
        No matter how you got here. You are here.
        {% endblock %}
    </div>
    <script>
        function beHere(when) {
            // TODO: add a template variable to set the URL prefix.
            window.location.href = `/presence/here?when=${when}`;
        }
    </script>
</body>

</html>
```


** Our task is  to populate each card with data from the backend model.**

Backend Data Models in SQLAlchemy. The data is *already* indexed in sql query.:
```
    class ParsedEventTable(Base):  # type: ignore
        """
        Table that holds the top level event and parsing info parsed from unstructured event data.
        """

        __tablename__ = "parsed_events"

        id = Column(Integer, primary_key=True)
        name = Column(String, nullable=True)
        description = Column(String, nullable=True)
        event_json = Column(JSON, nullable=True)
        original_event = Column(Text, nullable=False)
        failure_reason = Column(String, nullable=True)
        filename = Column(String, nullable=False)
        chat_history = Column(JSON, nullable=True)
        replay_history = Column(JSON, nullable=True)
        version = Column(String, nullable=False)
        parsed_event_embedding = relationship(  # type: ignore
            "ParsedEventEmbeddingsTable",
            uselist=False,
            back_populates="parsed_event",
        )
        geo_addresses = relationship(  # type: ignore
            "GeoAddresses", back_populates="related_parsed_events"
        )
        sub_mood_event = relationship(
            "SubMoodEventTable", back_populates="parsed_events", uselist=False
        )


    class GeoAddresses(Base):  # type: ignore
        __tablename__ = "GeoAddresses"
        id = Column(Integer, primary_key=True)
        parsed_event_id = Column(Integer, ForeignKey("parsed_events.id"))
        address = Column(String, nullable=False)
        latitude = Column(Float, nullable=True)
        longitude = Column(Float, nullable=True)
        failure_reason = Column(String, nullable=True)
        related_parsed_events = relationship(  # type: ignore
            "ParsedEventTable", back_populates="geo_addresses"
        )

    
    class MoodSubmoodTable(Base):  # type: ignore
        __tablename__ = "MoodSubMoodTable"
        id = Column(
            Integer, primary_key=True, autoincrement=True
        )  # Unique for the pair of mood submood
        mood = Column(Text, nullable=False)
        submood = Column(Text, nullable=False)


    class SubMoodEventTable(Base):  # type: ignore
        __tablename__ = "SubMoodEventTable"
        event_id = Column(Integer, ForeignKey("parsed_events.id"), primary_key=True)
        mood_sub_mood_id = Column(
            Integer, ForeignKey("MoodSubMoodTable.id"), primary_key=True
        )
        complete_json = Column(
            Text, nullable=False
        )  # Stores the actual json response from ai.

        parsed_events = relationship(  # type: ignore
            "ParsedEventTable", back_populates="sub_mood_event"
        )

```

    Where The event_json uis created from the following pydantic structure:
    ```
    class EventJson(BaseModel ):
        model_config = ConfigDict(extra="forbid")

        name: str
        # More information summarizing the event, services offered, te
        description: str
        categories: list
        # TODO: Type might reflect ontology of events when we have it.
        addresses: Optional[List[str]] = Field(
            default=None,
        )
        # Like a museum, restaurant advertizing its services or new services.
        is_ongoing: bool = Field(
            default=False,
        )
        # The event's start date(which can be after the date time of the document) If the event is ongoing then start and end dates are moot.
        start_date: Optional[List[datetime.date]] = Field(
            default=None,
        )
        end_date: Optional[List[datetime.date]] = Field(
            default=None,
        )
        start_time: Optional[List[datetime.time]] = Field(
            default=None,
        )
        end_time: Optional[List[datetime.time]] = Field(
            default=None,
        )
        # means no payment, event is free and payment_mode will be None
        is_paid: bool = Field(
            default=False,
        )
        has_promotion: bool = Field(
            default=False,
        )
        promotion_details: Optional[str] = Field(
            default=None,
        )
        payment_mode: Optional[PaymentMode] = Field(
            default=None,
        )

        payment_details: Optional[str] = Field(
            default=None,
        )
        links: Optional[List[str]] = Field(default=None)
    ```

I have used the above models to return the data needed for the jinja2 template using the following set of methods:
```

def geotag_moodtag_events(
    ctx: typer.Context,
    filename: str,
    version: str,
    where_lat: float,
    where_lon: float,
    when: When = When.NOW,
    now_window_hours: int = 1,
    stubbed_now: Optional[datetime] = None,
):
    datetime_now = stubbed_now or datetime.now()
    events: List[ParsedEventTable] = fetch_events_geocoded_mood_attached(
        ctx,
        filename,
        version,
        columns=[
            ParsedEventTable.id,
            ParsedEventTable.event_json,
            ParsedEventTable.name,
            ParsedEventTable.description,
            GeoAddresses.latitude,
            GeoAddresses.longitude,
            MoodSubmoodTable.mood,
            MoodSubmoodTable.submood,
        ],
    )

    # Calculate the time threshold
    filtered_events = []
    for event in events:
        if event.event_json and should_include_event(
            when,
            datetime_now,
            now_window_hours,
            cast(Dict[str, Any], event.event_json),
        ):
            assert event.latitude and event.longitude
            event_lat: float = event.latitude
            event_long: float = event.longitude
            # N2S: Could be lazy loaded by the web framework if found to be slow.
            directions = get_transit_distance_duration(
                where_lat, where_lon, event_lat, event_long
            )

            filtered_events.append(
                {
                    "event": event,
                    "directions": directions,
                }
            )

    return filtered_events


@session_manager
def fetch_events_geocoded_mood_attached(
    session,
    filename: str,
    version: str,
    columns: Optional[List[Column]] = [],
) -> List[ParsedEventTable]:
    """
    Fetches events from the database based on filename and version,
    and obtains the latitude and longitude of each event from the GeoAddresses table.

    Parameters:
    - db (Session): The database session.
    - filename (str): The filename to filter events on.
    - version (str): The version to filter events on.
    - lat (float): Latitude of the reference location.
    - long (float): Longitude of the reference location.

    Returns:
    - List[models.ParsedEventTable]: A list of events.
    """
    # Build the base query
    query = (
        session.query(ParsedEventTable, GeoAddresses, MoodSubmoodTable)
        .join(GeoAddresses, ParsedEventTable.id == GeoAddresses.parsed_event_id)
        .join(
            SubMoodEventTable, ParsedEventTable.id == SubMoodEventTable.event_id
        )
        .join(
            MoodSubmoodTable,
            SubMoodEventTable.mood_sub_mood_id == MoodSubmoodTable.id,
        )
        .filter(ParsedEventTable.filename == filename)
        .filter(ParsedEventTable.version == version)
        .filter(GeoAddresses.latitude.isnot(None))
        .filter(GeoAddresses.longitude.isnot(None))
    )
    if columns:
        query = query.with_entities(*columns)

    # Fetch and return the events
    events = query.all()
    return [e for e in events]  # pylint: disable=unnecessary-comprehension
def compute_hours_diff(
    start_date_str: str,
    end_date_str: str,
    start_time_str: str,
    end_time_str: str,
    datetime_now: datetime,
):
    # Default to full day if time is not provided
    start_time_str = start_time_str or "00:00"
    end_time_str = end_time_str or "23:59"

    # Combine date and time strings into datetime objects
    start_datetime_str = f"{start_date_str} {start_time_str}"
    end_datetime_str = f"{end_date_str} {end_time_str}"

    # Convert to datetime objects
    start_datetime = datetime.strptime(start_datetime_str, "%Y-%m-%d %H:%M")
    end_datetime = datetime.strptime(end_datetime_str, "%Y-%m-%d %H:%M")

    # Compute hours difference from datetime_now
    hours_from_now_start = (
        start_datetime - datetime_now
    ).total_seconds() / 3600
    hours_from_now_end = (end_datetime - datetime_now).total_seconds() / 3600
    has_already_started = start_datetime <= datetime_now
    has_already_ended = end_datetime < datetime_now

    return (
        hours_from_now_start,
        hours_from_now_end,
        has_already_started,
        has_already_ended,
    )


def should_include_event(
    when: When,
    datetime_now: datetime,
    now_window: int,
    event_json: Dict[str, Any],
) -> bool:
    # Check if the event is marked as ongoing

    # Get date and time fields from event_json
    start_dates = event_json.get("start_date", []) or []
    end_dates = event_json.get("end_date", []) or []
    start_times = event_json.get("start_time", []) or []
    end_times = event_json.get("end_time", []) or []

    if (start_times and not start_dates) or (end_times and not end_dates):
        # IN valid data?
        # pylint: disable=logging-not-lazy
        msg = (
            f"Invalid data in event_json. Start times and End Times: {start_times}, {end_times}"
            + f" But end dates and start dates are empty for event: {event_json}"
        )
        logger.warning(msg)
        return False

    # If all date and time fields are null, skip this event
    if not any([start_dates, end_dates, start_times, end_times]):
        if event_json.get("is_ongoing", False):
            if when == When.NOW:
                return True

        return False

    max_occurrences = max(
        [len(start_dates), len(end_dates), len(start_times), len(end_times)]
    )
    for i in range(max_occurrences):
        start_date_str = (
            start_dates[i]
            if i < len(start_dates)
            else datetime_now.date().strftime(
                "%Y-%m-%d"
            )  # Assume the event starts now if its not mentioned
        )
        end_date_str = (
            end_dates[i] if i < len(end_dates) else start_date_str
        )  # default to start_date if end_date is not provided

        start_time_str = (
            start_times[i]
            if i < len(start_times)
            else (  # if the event does have a start_date then assume its a full day event starting at 00:00
                "00:00"
                if len(start_dates) < i
                else datetime_now.time().strftime(
                    "%H:%M"
                )  # else assume that since there is no event_start it starts at datetime_now, same as start_date
            )
        )
        end_time_str = end_times[i] if i < len(end_times) else "23:59"

        (
            hours_from_now_start,
            hours_from_now_end,
            has_already_started,
            has_already_ended,
        ) = compute_hours_diff(
            start_date_str,
            end_date_str,
            start_time_str,
            end_time_str,
            datetime_now,
        )

        if has_already_started and not has_already_ended:
            if when == When.NOW:
                return True
            return False

        if has_already_ended:
            return False

        if when == When.NOW:
            condition_now = (hours_from_now_start <= now_window) or (
                hours_from_now_end >= 0 and hours_from_now_end <= now_window
            )
            if condition_now:
                return True
        else:  # when == When.LATER
            condition_later = hours_from_now_start > now_window
            if condition_later:
                return True

    return False

```


Requirements: 
1. Group events by submood and throw them into a list of lists ordering each list by when it happens. 
the lists are ordered by Submood. This is done in the here() route. 

The swipers are templated as follows from the data returned from geotag_moodtag_events:
```
    <!-- Swipper -->
        <div> Submood </div> Title of the swiper and remains static even as the slides are swiped into view.
        <!--Slide1 --> 
        <div> Mood </div> 
        <div> Name </div>
        <div> Description...</div> -> Clickable to expand in a small pop out
            <div class="popout"> -> This will be the popout
                <div> Name </div>
                <div> Description </div>
                <div> When: ___ hours from now or Mins from now </div>
                <div> Distance: ___ miles from here. </div> -> Calculate from the distance returned by geotag_moodtag_events
                <div> Where: ___ address. </div>
                <div> Links: ___ . </div>
            </div>
        </div>    
        <div> In 1 hours and 2 miles away on foot from you. </div> -> Create a method to summarize this from the directions  summary returned by geotag_moodtag_events
        <!--Slide2 --> 
        <div> Mood </div>
        <div> Name </div>
        <div> Description...</div> -> Clickable to expand in a small pop out
            <div class="popout"> -> This will be the popout
                <div> Name </div>
                <div> Description </div>
                <div> When: ___ hours from now or Mins from now </div>
                <div> Distance: ___ miles from here. </div>
                <div> Where: ___ address. </div>
                <div> Links: ___ . </div>
            </div>
        </div>    
        <div> In 30 minutes 1/2 a mile away on foot from you. </div> 
    <!-- End swiper -->
    <!-- More swipers to follow -->
```
2. If there are no events gotten from geotag_moodtag_events given the `when` argument in the here(..) route, 
then change the jinja template to display a warning like: "There are no events happening 'now', try events happening 'later'".
3. The directions from  geotag_moodtag_events can be null. Leave them empty in the template.
3. Each slide has to be of a fixed width and height. The poput has a fixed width and the content can 
flow in the column direction.
    3.1. Back ground color for each with a nice color theme for each color and a dark background.

Ask any clarifying questions first and then progress to the first step. Progress to the next step only after asking me and getting a go ahead and if your questions are answered.
 **ASK** me after each step what the final design is. **Ignore** intermediate chat between steps and only consider the final design as input for remaining steps.