from sqlalchemy import create_engine  # type: ignore[import]
from sqlalchemy.orm import sessionmaker  # type: ignore[import]

db_url = "postgresql://postgres:kanna@localhost:5432/chary"
engine =  create_engine(db_url)
session = sessionmaker(autocommit=False,autoflush=False,bind=engine)