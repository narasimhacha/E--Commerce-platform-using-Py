import unittest
from routers import ai as ai_module
from routers.ai_service import AIServiceError
from conftest import auth_header


def url(item_id):
    return f"/ai/cart/{item_id}/explain-price"


def fake_ai(payload):
    def _fake(system_prompt, user_prompt):
        return payload
    return _fake


BASE_REPLY = {"explanation": "Great laptop.", "key_features": ["Fast", "Light"], "alternatives": []}


# ---------- auth / access control ----------

def test_no_token_returns_401(client, world):
    assert client.post(url(world["item"].id)).status_code == 401


def test_admin_token_returns_403(client, world, monkeypatch):
    monkeypatch.setattr(ai_module, "generate_json", fake_ai(BASE_REPLY))
    # admin id deliberately equals alice's id to mimic the id-collision the code comments mention
    h = auth_header("root", world["alice"].id, role="admin")
    r = client.post(url(world["item"].id), headers=h)
    assert r.status_code == 403


def test_other_users_cart_item_returns_404(client, world, monkeypatch):
    monkeypatch.setattr(ai_module, "generate_json", fake_ai(BASE_REPLY))
    h = auth_header("bob", world["bob"].id)
    r = client.post(url(world["item"].id), headers=h)  # item belongs to alice
    assert r.status_code == 404


def test_missing_item_returns_404(client, world, monkeypatch):
    monkeypatch.setattr(ai_module, "generate_json", fake_ai(BASE_REPLY))
    h = auth_header("alice", world["alice"].id)
    assert client.post(url(99999), headers=h).status_code == 404


# ---------- happy path ----------

def test_returns_valid_alternative_with_db_name_and_price(client, world, monkeypatch):
    payload = dict(BASE_REPLY, alternatives=[
        {"product_id": world["phone"].id, "why_cheaper": "Smaller", "tradeoffs": "No keyboard"}
    ])
    monkeypatch.setattr(ai_module, "generate_json", fake_ai(payload))
    r = client.post(url(world["item"].id), headers=auth_header("alice", world["alice"].id))
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Laptop" and body["price"] == 50000.0
    assert body["explanation"] == "Great laptop."
    assert len(body["alternatives"]) == 1
    alt = body["alternatives"][0]
    assert alt["product_id"] == world["phone"].id
    assert alt["name"] == "Phone" and alt["price"] == 20000.0


def test_empty_alternatives_is_cold_start_fallback(client, world, monkeypatch):
    monkeypatch.setattr(ai_module, "generate_json", fake_ai(BASE_REPLY))
    r = client.post(url(world["item"].id), headers=auth_header("alice", world["alice"].id))
    assert r.status_code == 200
    assert r.json()["alternatives"] == []


# ---------- hallucination guard ----------

def test_unknown_product_id_is_dropped(client, world, monkeypatch):
    payload = dict(BASE_REPLY, alternatives=[
        {"product_id": 9999, "why_cheaper": "x", "tradeoffs": "y"}
    ])
    monkeypatch.setattr(ai_module, "generate_json", fake_ai(payload))
    r = client.post(url(world["item"].id), headers=auth_header("alice", world["alice"].id))
    assert r.status_code == 200
    assert r.json()["alternatives"] == []


def test_duplicate_ids_are_deduplicated(client, world, monkeypatch):
    alt = {"product_id": world["phone"].id, "why_cheaper": "a", "tradeoffs": "b"}
    monkeypatch.setattr(ai_module, "generate_json", fake_ai(dict(BASE_REPLY, alternatives=[alt, alt])))
    r = client.post(url(world["item"].id), headers=auth_header("alice", world["alice"].id))
    assert len(r.json()["alternatives"]) == 1


def test_ids_outside_candidate_set_are_dropped(client, world, monkeypatch):
    """out-of-stock, below price band, more expensive, or the cart product itself"""
    for key in ["tablet", "charger", "pricey", "laptop"]:
        alt = {"product_id": world[key].id, "why_cheaper": "a", "tradeoffs": "b"}
        monkeypatch.setattr(ai_module, "generate_json", fake_ai(dict(BASE_REPLY, alternatives=[alt])))
        r = client.post(url(world["item"].id), headers=auth_header("alice", world["alice"].id))
        assert r.status_code == 200
        assert r.json()["alternatives"] == []


def test_model_cannot_override_name_or_price(client, world, monkeypatch):
    alt = {"product_id": world["phone"].id, "name": "FAKE", "price": 1, "why_cheaper": "a", "tradeoffs": "b"}
    monkeypatch.setattr(ai_module, "generate_json", fake_ai(dict(BASE_REPLY, alternatives=[alt])))
    r = client.post(url(world["item"].id), headers=auth_header("alice", world["alice"].id))
    got = r.json()["alternatives"][0]
    assert got["name"] == "Phone" and got["price"] == 20000.0


# ---------- failure handling ----------

def test_ai_failure_returns_503(client, world, monkeypatch):
    def boom(*a, **k):
        raise AIServiceError("down")
    monkeypatch.setattr(ai_module, "generate_json", boom)
    r = client.post(url(world["item"].id), headers=auth_header("alice", world["alice"].id))
    assert r.status_code == 503


# ---------- ai_service ----------

def test_service_without_api_key_raises(monkeypatch):
    from routers import ai_service
    monkeypatch.setattr(ai_service, "_client", None)
    with unittest.TestCase().assertRaises(AIServiceError):
        ai_service.generate_json("s", "u")


def test_service_invalid_json_raises(monkeypatch):
    from routers import ai_service

    class R: text = "not json"
    class M:
        def generate_content(self, **k): return R()
    class C: models = M()
    monkeypatch.setattr(ai_service, "_client", C())
    with unittest.TestCase().assertRaisesRegex(AIServiceError, "invalid JSON"):
        ai_service.generate_json("s", "u")


def test_service_valid_json_parsed(monkeypatch):
    from routers import ai_service

    class R: text = '{"a": 1}'
    class M:
        def generate_content(self, **k): return R()
    class C: models = M()
    monkeypatch.setattr(ai_service, "_client", C())
    assert ai_service.generate_json("s", "u") == {"a": 1}


def test_service_provider_exception_wrapped(monkeypatch):
    from routers import ai_service

    class M:
        def generate_content(self, **k): raise RuntimeError("quota")
    class C: models = M()
    monkeypatch.setattr(ai_service, "_client", C())
    with unittest.TestCase().assertRaisesRegex(AIServiceError, "quota"):
        ai_service.generate_json("s", "u")