from typing import Annotated
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import joinedload

from app.models import (
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Product,
    Users,
    cartItem,
)
from app.order_schemas import (
    OrderDetailResponse,
    OrderItemSummary,
    PaymentRequest,
    PaymentResponse,
)
from app.payment_provider import GatewayResult, PaymentProvider, get_payment_provider
from routers.auth import db_dependency, get_current_user

router = APIRouter(tags=["payment"])
user_dependency = Annotated[dict, Depends(get_current_user)]
provider_dependency = Annotated[PaymentProvider, Depends(get_payment_provider)]


def _owned_order(order_id: int, user: dict, db) -> Order:
    order = (
        db.query(Order)
        .options(joinedload(Order.items), joinedload(Order.payments))
        .filter(Order.id == order_id)
        .first()
    )
    if not order or (user.get("role") != "admin" and order.user_id != user.get("id")):
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def _payment_result(order: Order, payment: Payment | None, reason: str | None = None) -> PaymentResponse:
    return PaymentResponse(
        order_id=order.id,
        order_status=order.status,
        payment_status=payment.status.value if payment else None,
        transaction_id=payment.transaction_id if payment else None,
        failure_reason=reason or (payment.failure_reason if payment else None),
    )


def _record_failure(
    db,
    order_id: int,
    method: PaymentMethod,
    reason: str,
    card_number: str | None = None,
    card_brand: str | None = None,
) -> PaymentResponse:
    order = db.query(Order).filter(Order.id == order_id).with_for_update().one()
    payment = Payment(
        order_id=order.id,
        method=method,
        status=PaymentStatus.FAILED,
        failure_reason=reason,
        card_last4=card_number[-4:] if card_number else None,
        card_brand=card_brand,
    )
    order.status = OrderStatus.FAILED
    db.add(payment)
    db.commit()
    db.refresh(order)
    db.refresh(payment)
    return _payment_result(order, payment)


@router.get("/payment/sandbox/{order_id}", response_model=OrderDetailResponse)
def get_sandbox_order(order_id: int, user: user_dependency, db: db_dependency):
    order = _owned_order(order_id, user, db)
    return OrderDetailResponse(
        order_id=order.id,
        subtotal=order.subtotal,
        tax=order.tax,
        shipping_fee=order.shipping_fee,
        cod_fee=order.cod_fee,
        discount=order.discount,
        total=order.total,
        payment_method=order.payment_method,
        status=order.status,
        created_at=order.created_at,
        items=[
            OrderItemSummary(
                product_id=item.product_id,
                product_name=item.product_name_snapshot,
                unit_price=item.unit_price_snapshot,
                quantity=item.quantity,
                line_total=item.unit_price_snapshot * item.quantity,
            )
            for item in order.items
        ],
        payments=order.payments,
    )


@router.post("/payment/sandbox/pay", response_model=PaymentResponse)
def pay_sandbox_order(
    request: PaymentRequest,
    order_id: int,
    user: user_dependency,
    db: db_dependency,
    provider: provider_dependency,
):
    order = _owned_order(order_id, user, db)

    if order.status == OrderStatus.PAID:
        existing = next(
            (payment for payment in order.payments if payment.status == PaymentStatus.SUCCEEDED),
            None,
        )
        return _payment_result(order, existing)
    if order.status == OrderStatus.COD_CONFIRMED:
        return _payment_result(order, None)
    if order.status != OrderStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot pay an order with status {order.status.value}",
        )

    method = order.payment_method
    card_number = None
    if method == PaymentMethod.CARD:
        if not all((request.card_number, request.cardholder_name, request.expiry, request.cvv)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Card number, cardholder name, expiry, and CVV are required",
            )
        if not re.fullmatch(r"[0-9 -]+", request.card_number):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Card number may contain only digits, spaces, and hyphens",
            )
        card_number = "".join(character for character in request.card_number if character.isdigit())
    elif method == PaymentMethod.ONLINE:
        if request.online_method == "UPI":
            if not request.upi_id:
                raise HTTPException(status_code=422, detail="UPI ID is required")
        elif request.online_method == "NETBANKING":
            if not request.bank_name:
                raise HTTPException(status_code=422, detail="Select a bank for netbanking")
            if request.bank_name not in {
                "State Bank of India",
                "HDFC Bank",
                "ICICI Bank",
                "Axis Bank",
            }:
                raise HTTPException(status_code=422, detail="Select a supported test bank")
        else:
            raise HTTPException(status_code=422, detail="Select UPI or netbanking")
    elif method != PaymentMethod.COD:
        raise HTTPException(status_code=422, detail="Unsupported payment method")

    if method == PaymentMethod.COD:
        gateway_result = GatewayResult(succeeded=True)
    else:
        gateway_result = provider.process(
            method,
            card_number=card_number,
            expiry=request.expiry,
            upi_id=request.upi_id if request.online_method == "UPI" else None,
        )

    if not gateway_result.succeeded:
        db.rollback()
        return _record_failure(
            db,
            order.id,
            method,
            gateway_result.failure_reason or "Payment failed",
            card_number,
            gateway_result.card_brand,
        )

    try:
        order = db.query(Order).filter(Order.id == order.id).with_for_update().one()
        if order.status != OrderStatus.PENDING:
            db.rollback()
            order = db.query(Order).filter(Order.id == order.id).one()
            if order.status == OrderStatus.PAID:
                existing = db.query(Payment).filter(
                    Payment.order_id == order.id,
                    Payment.status == PaymentStatus.SUCCEEDED,
                ).first()
                return _payment_result(order, existing)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot pay an order with status {order.status.value}",
            )

        items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        for item in items:
            updated = (
                db.query(Product)
                .filter(Product.id == item.product_id, Product.quantity >= item.quantity)
                .update(
                    {Product.quantity: Product.quantity - item.quantity},
                    synchronize_session=False,
                )
            )
            if not updated:
                raise ValueError(f"Insufficient stock for {item.product_name_snapshot}")

        db.query(cartItem).filter(cartItem.user_id == order.user_id).delete(
            synchronize_session=False
        )
        order.status = (
            OrderStatus.COD_CONFIRMED if method == PaymentMethod.COD else OrderStatus.PAID
        )
        payment = None
        if method != PaymentMethod.COD:
            payment = Payment(
                order_id=order.id,
                method=method,
                status=PaymentStatus.SUCCEEDED,
                card_last4=card_number[-4:] if card_number else None,
                card_brand=gateway_result.card_brand,
            )
            db.add(payment)
        db.commit()
        db.refresh(order)
        if payment:
            db.refresh(payment)
        return _payment_result(order, payment)
    except ValueError as error:
        db.rollback()
        return _record_failure(db, order.id, method, str(error), card_number, gateway_result.card_brand)
    except Exception:
        db.rollback()
        raise


@router.get("/orders/{order_id}", response_model=OrderDetailResponse)
def get_order(order_id: int, user: user_dependency, db: db_dependency):
    order = _owned_order(order_id, user, db)
    return get_sandbox_order(order.id, user, db)
