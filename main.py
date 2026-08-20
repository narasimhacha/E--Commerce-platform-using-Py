#We installed web framework as Fast api and web server as uvicorn. We will use Fast api to create a web application and uvicorn to run the application.
from typing import Annotated, List
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from fastapi import FastAPI, HTTPException, Depends, status
from models import Product, ProductSchema
from Database_config.database import Base,engine, session
import auth
from auth import get_current_user, db_dependency,require_admin
from models import Admins

app = FastAPI()
app.include_router(auth.router)

@app.get("/")
def ensure_user_email_column():
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "email" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255) UNIQUE"))
def ensure_user_role_column():
    inspector = inspect(engine)
    if "role" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "role" not in columns:
            with engine.begin() as connection: #begin considers the process as a transaction, if there is no error in the process then it commits transaction directly into DB.
                connection.execute(
                    text("ALTER TABLE users ADD COLUMN role VARCHAR(50) NOT NULL DEFAULT 'user'")
                )
ensure_user_role_column()
ensure_user_email_column()


Base.metadata.create_all(bind=engine)

sample_products = [
    {"id": 1, "name": "Laptops", "description": "ACER laptop Ryzen processor", "quantity": 10, "price": 50000.0},
    {"id": 2, "name": "Phone", "description": "Oppo f23 snap dragon processor", "quantity": 10, "price": 20000.0},
    {"id": 3, "name": "Headphones", "description": "Boat headphones with good sound quality", "quantity": 10, "price": 2000.0},
    {"id": 4, "name": "Charger", "description": "Mobile Charger", "quantity": 10, "price": 200.0},
]


def seed_data() :
    db = session()
    yield db
    try:
        if not db.query(Product).first():
            for item in sample_products:
                db.add(Product(**item))
            db.commit()
    finally:
        db.close()



seed_data()


@app.get("/", response_model=dict)
def greet():
    return {"message": "Welcome to Amazon"}


@app.get("/products", response_model=List[ProductSchema])
def get_all_products(db:Session = Depends(seed_data)):
    db = session()
    db_products = db.query(Product).all()
    
    return db_products

@app.get("/products/{product_id}", response_model=ProductSchema)
def get_product_by_id(product_id: int):
    db = session()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
    finally:
        db.close()


@app.post("/products", response_model=ProductSchema)
def add_product(new_product: ProductSchema, admin : dict = Depends(require_admin)):
    db = session()
    try:
        db_product = Product(**new_product.model_dump(exclude_unset=True))
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        return db_product
    finally:
        db.close()


@app.put("/products/{product_id}", response_model=ProductSchema)
def update_product(product_id: int, updated_product: ProductSchema,admin:dict = Depends(require_admin)):
    db = session()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        product.name = updated_product.name
        product.description = updated_product.description
        product.quantity = updated_product.quantity
        product.price = updated_product.price
        db.commit()
        db.refresh(product)
        return product
    finally:
        db.close()


@app.delete("/products/{product_id}")
def delete_product(product_id: int , admin :dict = Depends(require_admin)):
    db = session()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        db.delete(product)
        db.commit()
        return {"message": "Deletion successful"}
    finally:
        db.close()

user_dependency = Annotated[dict,Depends(get_current_user)]

@app.get("/", status_code=status.HTTP_200_OK)
async def user(user:user_dependency,db:db_dependency):
    if user is None:
        raise HTTPException(status_code=401,detail = 'Authentication Failed')
    return {"User":user}