from sqlalchemy import create_engine  # type: ignore[import]
from sqlalchemy.orm import sessionmaker, DeclarativeBase # type: ignore[import]
# for mapping and ORM we use sqlalchemy which is python lang


db_url = "mysql+pymysql://root:mysql@localhost:3306/e_commerce_db"
engine =  create_engine(
    db_url,
    echo = True
    )
session = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
    )
class Base(DeclarativeBase):
    pass