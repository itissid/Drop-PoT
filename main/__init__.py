from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base

# Import or define your models
from model.persistence_model import (
    ParsedEventTable,
)  # assuming EventTable is defined in models module of myapp package
import logging 

Base = declarative_base()

logger = logging.getLogger('sqlalchemy.engine')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(handler)

engine = create_engine("sqlite:///drop.sqlite", echo=True, future=True)

# Create tables in the database (if they do not exist yet)
Base.metadata.create_all(engine)
