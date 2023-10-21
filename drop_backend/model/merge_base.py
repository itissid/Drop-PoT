from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


def bind_engine(engine):
    Base.metadata.bind = engine
    Session.configure(bind=engine)


Base = declarative_base()
Session = sessionmaker()
