#We installed web framework as Fast api and web server as uvicorn. We will use Fast api to create a web application and uvicorn to run the application.
from typing import List
from sqlalchemy.orm import Session
from fastapi import FastAPI, HTTPException, Depends
from models import Product, ProductSchema
from Database_config.database import Base,engine, session


app = FastAPI()

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
def add_product(new_product: ProductSchema):
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
def update_product(product_id: int, updated_product: ProductSchema):
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
def delete_product(product_id: int):
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

