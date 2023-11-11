import json

from sqlalchemy import MetaData, Table, create_engine, select, update

# Create engine and reflect metadata
engine = create_engine("sqlite:///drop.db")
metadata = MetaData()
metadata.reflect(bind=engine)

# Access your table
table = metadata.tables["parsed_events"]

# Select rows with incorrectly stored JSON
with engine.connect() as conn:
    select_query = select(table).where(
        table.c.id > 278
    )  # Modify condition as needed
    results = conn.execute(select_query).fetchall()

    for row in results:
        # Deserialize and re-serialize the JSON data
        print(f"Original data:\n{row.event_json}, type: {type(row.event_json)}")
        # loaded_data = json.loads(row.event_json)
        # print(f"Corrected data:\n{loaded_data}, type: {type(loaded_data)}")

        # Updat)e the row with corrected data
        # row.event_json.pop("name")
        # row.event_json.pop("description")
        # update_query = (
        #     update(table)
        #     .where(table.c.id == row.id)
        #     .values(event_json=row.event_json)
        # )
        # conn.execute(update_query)
        # conn.commit()
