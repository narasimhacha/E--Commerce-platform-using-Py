from datetime import timedelta, datetime
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status
from Database_config.database import session as SessionLocal
from models import Users
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordRequestForm , OAuth2PasswordBearer
from jose import jwt, JWTError

router = APIRouter(
    prefix='/auth', 
    tags=['auth']
)

bcrcypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2_beare = OAuth2PasswordBearer(tokenUrl='auth/token')

SECRET_KEY = "Bgo9ZUmKrtDIezt5ysiF13Ct"
ALGORITHM = "HS256"

class CreateUserRequest(BaseModel):
    username : str
    email:str
    password: str

class Token(BaseModel):
    access_token:str
    token_type:str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

@router.post("/",status_code=status.HTTP_201_CREATED)
async def create_user(db: db_dependency,
                      create_user_request: CreateUserRequest):
    existing_user = db.query(Users).filter(
        (Users.username == create_user_request.username) |
        (Users.email == create_user_request.email)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )

    create_user_model = Users(
        username=create_user_request.username,
        email=create_user_request.email,
        hashed_password=bcrcypt_context.hash(create_user_request.password),
    )
    db.add(create_user_model)
    db.commit()
    db.refresh(create_user_model)

    return {
        "message": "User created successfully",
        "username": create_user_model.username,
        "email": create_user_model.email,
    }

@router.post("/token",response_model=Token)
async def login_for_access_token(form_data:Annotated[OAuth2PasswordRequestForm, Depends()],
    db:db_dependency):
    user = authenticate_user(form_data.username,form_data.password,db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="couldn't validate the user!!")
    token = create_access_token(user.username,user.id,timedelta(minutes= 20))
    return {'access_token':token,'token_type' : 'bearer'}
        
def authenticate_user(username:str,password:str,db):
    user = db.query(Users).filter(Users.username == username).first()
    if not user:
        return False
    if not bcrcypt_context.verify(password,user.hashed_password):
        return False
    return user

def create_access_token(
        username:str,
        user_id: int,
        expires_delta = timedelta
):
    encode = {'sub' : username,'id':user_id}
    expires = datetime.utcnow() + expires_delta
    encode.update({'exp':expires})
    return jwt.encode(encode,SECRET_KEY,algorithm=ALGORITHM)
