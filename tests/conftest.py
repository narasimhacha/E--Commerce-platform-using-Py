import os
import sys
import tempfile
from pathlib import Path

# Must be set BEFORE app modules are imported (database.py reads db_url at import time)
_tmp = tempfile.mkdtemp()
os.environ["db_url"] = f"sqlite:///{Path(_tmp) / 'test.db'}"
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ADMIN_SECRET_KEY", "test-admin-key")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # type: ignore[reportMissingImports]
from datetime import timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine, session
from app.models import Product, Users, cartItem
from routers.auth import create_access_token


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    s = session()
    try:
        yield s
    finally:
        s.close()


def token_for(username, user_id, role):
    return create_access_token(username, user_id, role, timedelta(minutes=5))


def auth_header(username, user_id, role="user"):
    return {"Authorization": f"Bearer {token_for(username, user_id, role)}"}


@pytest.fixture
def world(db):
    """Two users, a laptop in alice's cart, plus assorted cheaper products."""
    alice = Users(username="alice", email="a@x.com", hashed_password="x", role="user")
    bob = Users(username="bob", email="b@x.com", hashed_password="x", role="user")
    laptop = Product(name="Laptop", description="Ryzen laptop", quantity=5, price=50000.0)
    phone = Product(name="Phone", description="Snapdragon phone", quantity=5, price=20000.0)       # in band, in stock
    tablet = Product(name="Tablet", description="10 inch tablet", quantity=0, price=18000.0)        # in band, OUT of stock
    charger = Product(name="Charger", description="Mobile charger", quantity=5, price=200.0)        # below 30% band
    pricey = Product(name="Gaming PC", description="Big PC", quantity=5, price=90000.0)             # more expensive
    db.add_all([alice, bob, laptop, phone, tablet, charger, pricey])
    db.commit()
    for o in (alice, bob, laptop, phone, tablet, charger, pricey):
        db.refresh(o)
    item = cartItem(user_id=alice.id, product_id=laptop.id, quantity=1)
    db.add(item)
    db.commit()
    db.refresh(item)
    return dict(alice=alice, bob=bob, laptop=laptop, phone=phone, tablet=tablet,
                charger=charger, pricey=pricey, item=item)