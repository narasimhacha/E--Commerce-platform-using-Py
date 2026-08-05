from typing import Optional
from fastapi import HTTPException, status
from pydantic import BaseModel
#this is for pydantic
from sqlalchemy import Column, Integer, String, Float
#from sqlalchemy.orm import declarative_base
from Database_config.database import Base,engine

#Base = declarative_base()

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)


class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50),nullable=False,default="user")


class ProductSchema(BaseModel):
    id: Optional[int] = None
    name: str
    description: str
    quantity: int
    price: float

    model_config = {
    "from_attributes": True
    }


class UserSchema(BaseModel):
    username: str
    email: str
    password: str

    model_config = {
    "from_attributes": True
    }

#Base.metadata.create_all(bind=engine)
