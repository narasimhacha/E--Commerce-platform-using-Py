from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import joinedload

from app.models import Order, OrderItem, OrderStatus, PaymentMethod, Product, Users, cartItem
from app.order_schemas import CheckoutRequest, CheckoutResponse, OrderItemSummary
from routers.auth import db_dependency, get_current_user

router = APIRouter(tags=["checkout"])

user_dependency = Annotated[dict, Depends(get_current_user)]

GST_RATE = Decimal("0.18")
SHIPPING_FEE = Decimal("50.00")
COD_FEE = Decimal("30.00")
NO_DISCOUNT = Decimal("0.00")
CENT = Decimal("0.01")


def _money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
)
def checkout(
    request: CheckoutRequest,
    user: user_dependency,
    db: db_dependency,
):
    if user.get("role") == "admin" or not db.query(Users.id).filter(Users.id == user["id"]).first():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customer accounts can place orders",
        )

    cart_items = (
        db.query(cartItem)
        .options(joinedload(cartItem.product))
        .filter(cartItem.user_id == user["id"])
        .all()
    )
    if not cart_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot checkout with an empty cart",
        )

    subtotal = Decimal("0.00")
    order_item_summaries = []
    order_items = []

    for cart_item in cart_items:
        product: Product | None = cart_item.product
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Product {cart_item.product_id} is no longer available",
            )
        if cart_item.quantity <= 0 or cart_item.quantity > product.quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Insufficient stock for {product.name}; available quantity is {product.quantity}",
            )

        unit_price = _money(Decimal(str(product.price)))
        line_total = _money(unit_price * cart_item.quantity)
        subtotal += line_total
        order_items.append(
            OrderItem(
                product_id=product.id,
                product_name_snapshot=product.name,
                unit_price_snapshot=unit_price,
                quantity=cart_item.quantity,
            )
        )
        order_item_summaries.append(
            OrderItemSummary(
                product_id=product.id,
                product_name=product.name,
                unit_price=unit_price,
                quantity=cart_item.quantity,
                line_total=line_total,
            )
        )

    subtotal = _money(subtotal)
    tax = _money(subtotal * GST_RATE)
    shipping_fee = SHIPPING_FEE
    cod_fee = COD_FEE if request.payment_method == PaymentMethod.COD else NO_DISCOUNT
    discount = NO_DISCOUNT
    total = _money(subtotal + tax + shipping_fee + cod_fee - discount)

    order = Order(
        user_id=user["id"],
        subtotal=subtotal,
        tax=tax,
        shipping_fee=shipping_fee,
        cod_fee=cod_fee,
        discount=discount,
        total=total,
        payment_method=request.payment_method,
        status=OrderStatus.PENDING,
    )
    order.items = order_items
    db.add(order)
    db.commit()
    db.refresh(order)

    return CheckoutResponse(
        order_id=order.id,
        subtotal=subtotal,
        tax=tax,
        shipping_fee=shipping_fee,
        cod_fee=cod_fee,
        discount=discount,
        total=total,
        payment_method=order.payment_method,
        status=order.status,
        created_at=order.created_at,
        items=order_item_summaries,
    )
