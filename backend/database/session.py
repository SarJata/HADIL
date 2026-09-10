from sqlalchemy.ext.declarative import declarative_base
from .manager import db_manager

Base = declarative_base()

def get_db():
    db = db_manager.get_session()
    try:
        yield db
    finally:
        if db is not None:
            db.close()

def get_engine():
    return db_manager.engine
