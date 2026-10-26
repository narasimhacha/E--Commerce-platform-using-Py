import enum
import uuid
from typing import Optional
from pydantic import BaseModel
#this is for pydantic
from sqlalchemy import Column, Integer, String, Float, Numeric, DateTime, Enum as SQLAlchemyEnum, ForeignKey, func
#from sqlalchemy.orm import declarative_base
from app.database import Base,engine
from sqlalchemy.orm import relationship

#Base = declarative_base()

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    image_url = Column(String(1000), nullable=True)


class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50),nullable=True,default="user")

class Admins(Base):
    __tablename__ = "admins"

    id = Column(Integer,primary_key=True,nullable=False)
    username = Column(String(255),unique =  True, nullable=False)
    email = Column(String(255),unique=True,nullable=False)
    hashed_password = Column(String(255),nullable=False)
    role = Column(String(50), nullable = False, default ="admin" )

class cartItem(Base):
    __tablename__ = "cart_items"
    id = Column(Integer,primary_key=True,index=True)
    user_id = Column(Integer,ForeignKey("users.id"),nullable=False)
    product_id = Column(Integer,ForeignKey("products.id"),nullable=False)
    quantity = Column(Integer,nullable=False,default=1)

    product = relationship("Product")


class PaymentMethod(str, enum.Enum):
    CARD = "CARD"
    ONLINE = "ONLINE"
    COD = "COD"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    COD_CONFIRMED = "COD_CONFIRMED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


def generate_transaction_id() -> str:
    return f"MOCK-{uuid.uuid4().hex}"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    subtotal = Column(Numeric(12, 2), nullable=False)
    tax = Column(Numeric(12, 2), nullable=False)
    shipping_fee = Column(Numeric(12, 2), nullable=False, default=0)
    cod_fee = Column(Numeric(12, 2), nullable=False, default=0)
    discount = Column(Numeric(12, 2), nullable=False, default=0)
    total = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(
        SQLAlchemyEnum(
            PaymentMethod,
            name="payment_method",
            native_enum=False,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    status = Column(
        SQLAlchemyEnum(
            OrderStatus,
            name="order_status",
            native_enum=False,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        default=OrderStatus.PENDING,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    product_name_snapshot = Column(String(255), nullable=False)
    unit_price_snapshot = Column(Numeric(12, 2), nullable=False)
    quantity = Column(Integer, nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    method = Column(
        SQLAlchemyEnum(
            PaymentMethod,
            name="payment_method",
            native_enum=False,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    status = Column(
        SQLAlchemyEnum(
            PaymentStatus,
            name="payment_status",
            native_enum=False,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    transaction_id = Column(String(40), nullable=False, unique=True, default=generate_transaction_id)
    failure_reason = Column(String(255), nullable=True)
    card_last4 = Column(String(4), nullable=True)
    card_brand = Column(String(30), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    order = relationship("Order", back_populates="payments")


class ProductSchema(BaseModel):
    id: Optional[int] = None
    name: str
    description: str
    quantity: int
    price: float
    image_url: Optional[str] = None

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
class AdminSchema(BaseModel):
    username:str
    email: str
    password : str
    admin_key : str

    model_config = {
        "from_attributes" : True
    } 

class CartItemCreate(BaseModel):
    product_id : int
    quantity: int = 1

class CartItemUpdate(BaseModel):
    quantity: int

class CartItemSchema(BaseModel):
    id: int
    product_id:int
    quantity:int
    product: ProductSchema

    model_config = {
        "from_attributes" : True
    }

#Base.metadata.create_all(bind=engine)
###check admin features and roles 