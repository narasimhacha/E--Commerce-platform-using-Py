from pydantic import BaseModel

class Products(BaseModel):
    name : str
    id : int
    description : str
    quantity : int
    price : float
