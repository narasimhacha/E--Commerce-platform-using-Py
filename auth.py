from datetime import timedelta, datetime
from typing import Annotated
from Fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status
from database import SessionLocal
from models import Product
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordRequestForm , OAuth2PasswordBearer
from jose import jwt, JWTError

router = APIRouter{
    prefix='/auth'
    tags=['auth']
}