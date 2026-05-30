#We installed web framework as Fast api and web server as uvicorn. We will use Fast api to create a web application and uvicorn to run the application.
from fastapi import FastAPI
from models import Products
app = FastAPI()

@app.get("/")

def greet():
        return "Welcome to Amazon"

greet()


product = [
        
        Products(id =1,name="Laptops",description ="ACER laptop Ryzen processor",quantity=10,price = 50000),
        Products(id=2,name="Phone",description="Oppo f23 snap dragon processor",quantity=10,price=20000),
        Products(id=3,name="Headphones",description="Boat headphones with good sound quality",quantity=10,price=2000),
        Products(id=4,name="Charger",description="Mobile Charger",quantity=10,price=200)
        ]

        

@app.get("/products")
def get_all_products():
        return product

@app.get("/products/{id}")
def get_products_by_id(id:int):
        for i in product:
                if i.id == id:
                        return i
        return "product not found"

@app.post("/products")
def add_product(new_product:Products):
        product.append(new_product)
        return new_product

