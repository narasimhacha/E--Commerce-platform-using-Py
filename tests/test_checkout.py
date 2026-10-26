from decimal import Decimal

from app.models import Order, OrderItem, Product, cartItem
from tests.conftest import auth_header


def test_checkout_creates_price_snapshots_and_keeps_cart_and_stock(client, db, world):
    response = client.post(
        "/checkout",
        headers=auth_header("alice", world["alice"].id),
        json={"payment_method": "CARD"},
    )

    assert response.status_code == 201
    result = response.json()
    assert Decimal(result["subtotal"]) == Decimal("50000.00")
    assert Decimal(result["tax"]) == Decimal("9000.00")
    assert Decimal(result["shipping_fee"]) == Decimal("50.00")
    assert Decimal(result["cod_fee"]) == Decimal("0.00")
    assert Decimal(result["discount"]) == Decimal("0.00")
    assert Decimal(result["total"]) == Decimal("59050.00")
    assert result["items"] == [
        {
            "product_id": world["laptop"].id,
            "product_name": "Laptop",
            "unit_price": "50000.00",
            "quantity": 1,
            "line_total": "50000.00",
        }
    ]

    order = db.query(Order).filter(Order.id == result["order_id"]).one()
    order_item = db.query(OrderItem).filter(OrderItem.order_id == order.id).one()
    assert order.status.value == "PENDING"
    assert order_item.product_name_snapshot == "Laptop"
    assert float(order_item.unit_price_snapshot) == 50000
    assert db.query(cartItem).filter(cartItem.user_id == world["alice"].id).count() == 1
    assert db.query(Product).filter(Product.id == world["laptop"].id).one().quantity == 5

    world["laptop"].name = "Updated Laptop"
    world["laptop"].price = 70000
    db.commit()
    db.refresh(order_item)
    assert order_item.product_name_snapshot == "Laptop"
    assert float(order_item.unit_price_snapshot) == 50000


def test_checkout_rejects_empty_cart(client, db, world):
    db.query(cartItem).filter(cartItem.user_id == world["alice"].id).delete()
    db.commit()

    response = client.post(
        "/checkout",
        headers=auth_header("alice", world["alice"].id),
        json={"payment_method": "CARD"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot checkout with an empty cart"
    assert db.query(Order).count() == 0


def test_checkout_adds_cod_fee(client, world):
    response = client.post(
        "/checkout",
        headers=auth_header("alice", world["alice"].id),
        json={"payment_method": "COD"},
    )

    assert response.status_code == 201
    result = response.json()
    assert Decimal(result["cod_fee"]) == Decimal("30.00")
    assert Decimal(result["total"]) == Decimal("59080.00")


def test_checkout_rejects_stale_stock(client, db, world):
    world["laptop"].quantity = 0
    db.commit()

    response = client.post(
        "/checkout",
        headers=auth_header("alice", world["alice"].id),
        json={"payment_method": "COD"},
    )

    assert response.status_code == 409
    assert "Insufficient stock" in response.json()["detail"]
    assert db.query(Order).count() == 0
    assert db.query(cartItem).filter(cartItem.user_id == world["alice"].id).count() == 1
