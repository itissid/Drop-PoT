from functools import wraps

import click
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import create_database, database_exists # type: ignore


def validate_database(test_db: bool = False):
    obj = click.get_current_context().obj
    if test_db:
        url = "sqlite:///test_drop.db"
    else:
        url = "sqlite:///drop.db"
    print(f"Initalizing database at {url}")
    if not database_exists(url):  # Checks for the first time
        create_database(url)  # Create new DB
        print(
            "New Database Created: "
            + str(database_exists(obj.get("engine", url)))
        )  # Verifies if database is there or not.
    if not obj.get("engine"):
        obj["engine"] = create_engine(url)
    else:
        print("Engine already Exists")


def session_manager(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        engine = args[0].obj["engine"]  # Assuming the first argument is ctx
        session = sessionmaker(bind=engine)()
        try:
            result= func(session, *args[1:], **kwargs)
            session.commit()
            return result
        except Exception as exp:
            session.rollback()
            raise exp
        finally:
            session.close()

    return wrapper
