##this is for sqlalchemy
from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import declarative_base
#Indexing ----A database index is a separate, optimized data structure (most commonly a B-Tree) that speeds up data retrieval by allowing the database engine to find rows quickly without scanning the entire table

Base = declarative_base()

class Products(Base):
    __tablename__ ="product"
    id = Column(Integer, primary_key = True, Index = True)
    name = Column(String)
    description = Column(String)
    quantity =  Column(Integer)
    price = Column(Float)
