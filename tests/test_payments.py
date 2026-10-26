import pytest

from app.models import Payment, PaymentStatus, Product, cartItem
from app.payment_provider import MockGateway, get_payment_provider
from tests.conftest import auth_header


def create_order(client, world, method="CARD"):
    response = client.post(
        "/checkout",
        headers=auth_header("alice", world["alice"].id),
        json={"payment_method": method},
    )
    assert response.status_code == 201
    return response.json()["order_id"]


def test_card_success_decrements_stock_clears_cart_and_is_idempotent(
    client, db, world, app_fast_gateway
):
    order_id = create_order(client, world)
    headers = auth_header("alice", world["alice"].id)
    payload = {
        "card_number": "4111111111111111",
        "cardholder_name": "Alice Example",
        "expiry": "12/30",
        "cvv": "123",
    }

    first = client.post(
        f"/payment/sandbox/pay?order_id={order_id}", headers=headers, json=payload
    )
    second = client.post(
        f"/payment/sandbox/pay?order_id={order_id}", headers=headers, json=payload
    )

    assert first.status_code == 200
    assert first.json()["order_status"] == "PAID"
    assert first.json()["payment_status"] == "SUCCEEDED"
    assert second.json()["transaction_id"] == first.json()["transaction_id"]
    assert db.query(Payment).filter(Payment.order_id == order_id).count() == 1
    saved = db.query(Payment).filter(Payment.order_id == order_id).one()
    assert saved.card_last4 == "1111"
    assert saved.card_brand == "Visa"
    assert not hasattr(saved, "cvv")
    assert world["laptop"].quantity == 4
    assert db.query(cartItem).filter(cartItem.user_id == world["alice"].id).count() == 0


def test_declined_card_keeps_stock_and_cart(client, db, world, app_fast_gateway):
    order_id = create_order(client, world)
    response = client.post(
        f"/payment/sandbox/pay?order_id={order_id}",
        headers=auth_header("alice", world["alice"].id),
        json={
            "card_number": "4000000000000002",
            "cardholder_name": "Alice Example",
            "expiry": "12/30",
            "cvv": "123",
        },
    )

    assert response.status_code == 200
    assert response.json()["order_status"] == "FAILED"
    assert response.json()["failure_reason"] == "Declined: insufficient funds"
    assert db.query(Product).filter(Product.id == world["laptop"].id).one().quantity == 5
    assert db.query(cartItem).filter(cartItem.user_id == world["alice"].id).count() == 1
    payment = db.query(Payment).filter(Payment.order_id == order_id).one()
    assert payment.status == PaymentStatus.FAILED
    assert payment.card_last4 == "0002"


def test_invalid_luhn_card_is_rejected(client, world, app_fast_gateway):
    order_id = create_order(client, world)
    response = client.post(
        f"/payment/sandbox/pay?order_id={order_id}",
        headers=auth_header("alice", world["alice"].id),
        json={
            "card_number": "4111111111111112",
            "cardholder_name": "Alice Example",
            "expiry": "12/30",
            "cvv": "123",
        },
    )
    assert response.json()["failure_reason"] == "Invalid card number (Luhn check failed)"


def test_upi_failure_keeps_order_cart_and_stock(client, db, world, app_fast_gateway):
    order_id = create_order(client, world, "ONLINE")
    response = client.post(
        f"/payment/sandbox/pay?order_id={order_id}",
        headers=auth_header("alice", world["alice"].id),
        json={"online_method": "UPI", "upi_id": "fail@test"},
    )

    assert response.json()["order_status"] == "FAILED"
    assert response.json()["failure_reason"] == "UPI payment failed in test mode"
    assert db.query(Product).filter(Product.id == world["laptop"].id).one().quantity == 5
    assert db.query(cartItem).filter(cartItem.user_id == world["alice"].id).count() == 1


@pytest.mark.parametrize(
    ("card_number", "reason"),
    [
        ("4000000000000069", "Card expired"),
        ("4000000000000119", "Processing error; please try again"),
    ],
)
def test_mock_gateway_card_failure_scenarios(
    client, world, app_fast_gateway, card_number, reason
):
    order_id = create_order(client, world)
    response = client.post(
        f"/payment/sandbox/pay?order_id={order_id}",
        headers=auth_header("alice", world["alice"].id),
        json={
            "card_number": card_number,
            "cardholder_name": "Alice Example",
            "expiry": "12/30",
            "cvv": "123",
        },
    )
    assert response.json()["failure_reason"] == reason


def test_upi_success_and_netbanking_success(client, db, world, app_fast_gateway):
    headers = auth_header("alice", world["alice"].id)
    upi_order_id = create_order(client, world, "ONLINE")
    upi = client.post(
        f"/payment/sandbox/pay?order_id={upi_order_id}",
        headers=headers,
        json={"online_method": "UPI", "upi_id": "success@test"},
    )
    assert upi.json()["order_status"] == "PAID"

    db.expire_all()
    alice_id = world["alice"].id
    phone_id = world["phone"].id
    db.expunge_all()
    db.add(cartItem(user_id=alice_id, product_id=phone_id, quantity=1))
    db.commit()
    bank_order_id = create_order(client, world, "ONLINE")
    bank = client.post(
        f"/payment/sandbox/pay?order_id={bank_order_id}",
        headers=headers,
        json={"online_method": "NETBANKING", "bank_name": "HDFC Bank"},
    )
    assert bank.json()["order_status"] == "PAID"


def test_cod_confirms_order_without_payment_record(client, db, world, app_fast_gateway):
    order_id = create_order(client, world, "COD")
    response = client.post(
        f"/payment/sandbox/pay?order_id={order_id}",
        headers=auth_header("alice", world["alice"].id),
        json={},
    )

    assert response.json()["order_status"] == "COD_CONFIRMED"
    assert response.json()["payment_status"] is None
    assert db.query(Payment).filter(Payment.order_id == order_id).count() == 0
    assert world["laptop"].quantity == 4
    assert db.query(cartItem).filter(cartItem.user_id == world["alice"].id).count() == 0


def test_other_users_cannot_read_or_pay_order(client, world, app_fast_gateway):
    order_id = create_order(client, world)
    bob_headers = auth_header("bob", world["bob"].id)

    assert client.get(f"/orders/{order_id}", headers=bob_headers).status_code == 404
    assert client.get(
        f"/payment/sandbox/{order_id}", headers=bob_headers
    ).status_code == 404
    assert client.post(
        f"/payment/sandbox/pay?order_id={order_id}",
        headers=bob_headers,
        json={},
    ).status_code == 404


def test_orders_endpoint_returns_payment_status(client, world, app_fast_gateway):
    order_id = create_order(client, world)
    headers = auth_header("alice", world["alice"].id)
    client.post(
        f"/payment/sandbox/pay?order_id={order_id}",
        headers=headers,
        json={
            "card_number": "4111111111111111",
            "cardholder_name": "Alice Example",
            "expiry": "12/30",
            "cvv": "123",
        },
    )
    order = client.get(f"/orders/{order_id}", headers=headers)

    assert order.status_code == 200
    assert order.json()["status"] == "PAID"
    assert order.json()["payments"][0]["status"] == "SUCCEEDED"


def test_failed_order_cannot_be_paid_again(client, db, world, app_fast_gateway):
    order_id = create_order(client, world)
    headers = auth_header("alice", world["alice"].id)
    payload = {
        "card_number": "4000000000000002",
        "cardholder_name": "Alice Example",
        "expiry": "12/30",
        "cvv": "123",
    }
    client.post(f"/payment/sandbox/pay?order_id={order_id}", headers=headers, json=payload)
    retry = client.post(f"/payment/sandbox/pay?order_id={order_id}", headers=headers, json=payload)

    assert retry.status_code == 409
    assert db.query(Payment).filter(Payment.order_id == order_id).count() == 1


@pytest.fixture
def app_fast_gateway():
    from app.main import app

    app.dependency_overrides[get_payment_provider] = lambda: MockGateway((0, 0))
    yield
    app.dependency_overrides.pop(get_payment_provider, None)
