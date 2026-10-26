#We installed web framework as Fast api and web server as uvicorn. We will use Fast api to create a web application and uvicorn to run the application.
from typing import Annotated, List
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from fastapi import FastAPI, HTTPException, Depends, status
from app.models import Product, ProductSchema
from app.database import Base,engine, session
import routers.auth as auth
from routers.auth import get_current_user, db_dependency,require_admin
from app.models import Admins
import routers.cart as cart
from routers import auth, cart, ai, checkout, payments



app = FastAPI()
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(cart.router)
app.include_router(ai.router)
app.include_router(checkout.router)
app.include_router(payments.router)


def ensure_user_email_column():
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "email" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255) UNIQUE"))


def ensure_user_role_column():
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "role" not in columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE users ADD COLUMN role VARCHAR(50) NOT NULL DEFAULT 'user'")
                )


ensure_user_role_column()
ensure_user_email_column()


Base.metadata.create_all(bind=engine)

def ensure_product_image_column():
    inspector = inspect(engine)
    if "products" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("products")}
        if "image_url" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE products ADD COLUMN image_url VARCHAR(1000)"))


ensure_product_image_column()

sample_products = [
    {"id": 1, "name": "Laptops", "description": "ACER laptop Ryzen processor", "quantity": 10, "price": 50000.0,
     "image_url": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=1000&q=80"},
    {"id": 2, "name": "Phone", "description": "Oppo f23 snap dragon processor", "quantity": 10, "price": 20000.0,
     "image_url": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=1000&q=80"},
    {"id": 3, "name": "Headphones", "description": "Boat headphones with good sound quality", "quantity": 10, "price": 2000.0,
     "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=1000&q=80"},
    {"id": 4, "name": "Charger", "description": "Mobile Charger", "quantity": 10, "price": 200.0,
     "image_url": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1000&q=80"},
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
        product.image_url = updated_product.image_url
        db.commit()
        db.refresh(product)
        return product
    finally:
        db.close()


@app.delete("/products/{product_id}")
def delete_product(product_id: int, admin: dict = Depends(require_admin)):
    db = session()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # 1. delete the product
        db.delete(product)
        db.flush()

        # 2. move all later ids forward (6 -> 5, 7 -> 6, ...)
        db.execute(
            text("UPDATE products SET id = id - 1 WHERE id > :pid ORDER BY id"),
            {"pid": product_id},
        )
        db.commit()

        # 3. reset auto-increment so the next insert gets max id + 1
        next_id = db.execute(text("SELECT COALESCE(MAX(id), 0) + 1 FROM products")).scalar()
        db.execute(text(f"ALTER TABLE products AUTO_INCREMENT = {int(next_id)}"))
        db.commit()

        return {"message": "Deletion successful"}
    finally:
        db.close()
user_dependency = Annotated[dict,Depends(get_current_user)]

@app.get("/user", status_code=status.HTTP_200_OK)
async def user(user:user_dependency,db:db_dependency):
    if user is None:
        raise HTTPException(status_code=401,detail = 'Authentication Failed')
    return {"User":user}