import os

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").strip()
TOKEN = os.getenv("ADMIN_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_KEY = os.getenv("ADMIN_KEY")
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY")


def build_headers(token=None):
    headers = {}
    token = token or TOKEN
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def ensure_admin_token():
    global TOKEN

    if TOKEN:
        return TOKEN

    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        raise SystemExit(
            "No ADMIN_TOKEN set and no ADMIN_USERNAME/ADMIN_PASSWORD provided. "
            "Set ADMIN_TOKEN in .env or provide admin credentials."
        )

    login_response = requests.post(
        f"{BASE_URL}/auth/token",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        timeout=20,
    )

    if login_response.status_code == 200:
        TOKEN = login_response.json()["access_token"]
        return TOKEN

    if ADMIN_KEY or ADMIN_SECRET_KEY:
        admin_key = ADMIN_KEY or ADMIN_SECRET_KEY
        create_response = requests.post(
            f"{BASE_URL}/auth/register-admin",
            json={
                "username": ADMIN_USERNAME,
                "email": f"{ADMIN_USERNAME}@admin.local",
                "password": ADMIN_PASSWORD,
                "admin_key": admin_key,
            },
            timeout=20,
        )
        if create_response.status_code in (200, 201):
            login_response = requests.post(
                f"{BASE_URL}/auth/token",
                data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
                timeout=20,
            )
            if login_response.status_code == 200:
                TOKEN = login_response.json()["access_token"]
                return TOKEN

    raise SystemExit(
        "Unable to authenticate as admin. Provide a valid ADMIN_TOKEN or set ADMIN_USERNAME/ADMIN_PASSWORD plus ADMIN_SECRET_KEY."
    )


def fetch_products():
    response = requests.get(
        "https://dummyjson.com/products",
        params={"limit": 100},
        timeout=20,
    )
    response.raise_for_status()
    return response.json().get("products", [])


def map_product(product):
    description = product.get("description", "")
    brand = product.get("brand", "N/A")
    category = product.get("category", "Uncategorized")
    desc = f"{description} (Brand: {brand}, Category: {category})"
    return {
        "name": product.get("title", product.get("name", "Unnamed")),
        "description": desc[:1000],
        "quantity": int(product.get("stock", 0)),
        "price": float(product.get("price", 0)),
    }


def main():
    token = ensure_admin_token()
    headers = build_headers(token)

    try:
        existing_response = requests.get(f"{BASE_URL}/products", headers=headers, timeout=20)
        existing_response.raise_for_status()
    except requests.RequestException as exc:
        raise SystemExit(f"Unable to reach API at {BASE_URL}: {exc}") from exc

    if existing_response.status_code == 401:
        raise SystemExit("API rejected the admin token. Check ADMIN_TOKEN or admin credentials.")

    existing = existing_response.json()
    existing_names = {product["name"] for product in existing}

    created = skipped = failed = 0
    for src in fetch_products():
        payload = map_product(src)
        if payload["name"] in existing_names:
            skipped += 1
            continue

        response = requests.post(
            f"{BASE_URL}/products",
            json=payload,
            headers=headers,
            timeout=20,
        )
        if 200 <= response.status_code < 300:
            created += 1
        else:
            failed += 1
            print("FAILED", payload["name"], response.status_code, response.text[:150])

    print(f"created={created} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()