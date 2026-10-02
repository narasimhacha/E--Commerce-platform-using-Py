from sqlalchemy import create_engine  # type: ignore[import]
from sqlalchemy.orm import sessionmaker, DeclarativeBase # type: ignore[import]
# for mapping and ORM we use sqlalchemy which is python lang
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("db_url")
engine = create_engine(
    DATABASE_URL,
    echo=True
)
session = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
    )
class Base(DeclarativeBase):
    pass