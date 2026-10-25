from conftest import auth_header


def test_product_image_url_is_created_returned_and_updated(client):
    headers = auth_header("root", 1, role="admin")
    image_url = "https://example.com/product.jpg"
    product = {
        "name": "Camera",
        "description": "Compact digital camera",
        "quantity": 3,
        "price": 12000.0,
        "image_url": image_url,
    }

    created = client.post("/products", headers=headers, json=product)

    assert created.status_code == 200
    product_id = created.json()["id"]
    assert created.json()["image_url"] == image_url
    assert client.get(f"/products/{product_id}").json()["image_url"] == image_url

    updated_url = "https://example.com/updated-product.jpg"
    product["image_url"] = updated_url
    updated = client.put(f"/products/{product_id}", headers=headers, json=product)

    assert updated.status_code == 200
    assert updated.json()["image_url"] == updated_url


def test_product_image_url_is_optional(client, world):
    response = client.get(f"/products/{world['laptop'].id}")

    assert response.status_code == 200
    assert response.json()["image_url"] is None
