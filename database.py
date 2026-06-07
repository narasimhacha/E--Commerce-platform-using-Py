from sqlalchemy import create_engine  # type: ignore[import]
from sqlalchemy.orm import sessionmaker  # type: ignore[import]
# for mapping and ORM we use sqlalchemy which is python lang


db_url = "postgresql://postgres:kanna@localhost:5432/postgres"
engine =  create_engine(db_url)
session = sessionmaker(autocommit=False,autoflush=False,bind=engine)
