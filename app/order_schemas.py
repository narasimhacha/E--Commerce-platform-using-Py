from datetime import datetime
from decimal import Decimal

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import PaymentMethod, OrderStatus


class CheckoutRequest(BaseModel):
    payment_method: PaymentMethod = PaymentMethod.CARD


class OrderItemSummary(BaseModel):
    product_id: int
    product_name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


class CheckoutResponse(BaseModel):
    order_id: int
    subtotal: Decimal
    tax: Decimal
    shipping_fee: Decimal
    cod_fee: Decimal
    discount: Decimal
    total: Decimal
    payment_method: PaymentMethod
    status: OrderStatus
    created_at: datetime
    items: list[OrderItemSummary] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PaymentRequest(BaseModel):
    card_number: str | None = Field(default=None, min_length=12, max_length=23)
    cardholder_name: str | None = Field(default=None, min_length=2, max_length=100)
    expiry: str | None = Field(default=None, pattern=r"^(0[1-9]|1[0-2])\/\d{2}$")
    cvv: str | None = Field(default=None, pattern=r"^\d{3,4}$")
    online_method: Literal["UPI", "NETBANKING"] | None = None
    upi_id: str | None = Field(default=None, max_length=100)
    bank_name: str | None = Field(default=None, max_length=80)


class PaymentResponse(BaseModel):
    order_id: int
    order_status: OrderStatus
    payment_status: str | None
    transaction_id: str | None = None
    failure_reason: str | None = None


class PaymentSummary(BaseModel):
    id: int
    method: PaymentMethod
    status: str
    transaction_id: str
    failure_reason: str | None = None
    card_last4: str | None = None
    card_brand: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderDetailResponse(CheckoutResponse):
    payments: list[PaymentSummary] = Field(default_factory=list)
