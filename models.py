from typing import Optional

from pydantic import BaseModel
#this is for pydantic
from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import declarative_base
from database import engine

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)


class ProductSchema(BaseModel):
    id: Optional[int] = None
    name: str
    description: str
    quantity: int
    price: float

    class Config:
        orm_mode = True

Base.metadata.create_all(bind=engine)