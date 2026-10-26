# E-Commerce Platform (Python / FastAPI)

A backend REST API for a simple e-commerce platform, built with **FastAPI** and **SQLAlchemy**. It supports product browsing, JWT-based authentication, role-based authorization (admin vs. customer), and per-user shopping carts.

> This is a backend-only repository. It's designed to be paired with a separate frontend (e.g. a JavaScript/React client) that consumes these endpoints.

## Features

- **Authentication** — user registration and login using JWT (JSON Web Tokens), with passwords hashed via bcrypt.
- **Authorization (RBAC)** — every user has a role of `customer` or `admin`. Only admins can create, update, or delete products. Admin accounts can only be created by supplying a secret key set by the project owner (see [Environment Variables](#environment-variables)) — nobody can self-promote to admin at signup.
- **Product catalog** — public endpoints to browse products; admin-only endpoints to manage inventory.
- **Shopping cart** — authenticated users can add, view, update, and remove items from their own cart. Cart access is strictly scoped to the logged-in user; one user can never see or modify another user's cart.
- **Stock validation** — the cart won't let you add or update to a quantity that exceeds available stock.
- **AI-based product recommendations** — suggests products based on what's currently in a user's cart, using the Claude API. Recommendations are validated against the real product catalog before being returned, so the API can never surface a product that doesn't actually exist.

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI |
| ORM | SQLAlchemy |
| Auth | JWT (`python-jose`), password hashing via `passlib` (bcrypt) |
| Validation | Pydantic |
| Database | Any SQLAlchemy-supported DB (SQLite for local dev, PostgreSQL/MySQL for production) |

## Project Structure

```
.
├── main.py                        # App entrypoint, product routes, cart routes
├── auth.py                        # Registration, login, JWT creation/validation, RBAC dependencies
├── models.py                      # SQLAlchemy models + Pydantic schemas
├── Database_config/
│   ├── database.py                # Engine, session, declarative Base
│   └── database_models.py         # (legacy/unused duplicate model - see Known Issues)
├── requirements.txt
├── .env.example                   # Template for required environment variables
└── README.md
```

## Getting Started

### 1. Clone and install dependencies

```bash
git clone https://github.com/narasimhacha/E--Commerce-platform-using-Py.git
cd E--Commerce-platform-using-Py
python -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy the example file and fill in real values:

```bash
cp .env.example .env
```

### Environment Variables

| Variable | Description |
|---|---|
| `db_url` | SQLAlchemy database connection string. For quick local testing: `sqlite:///./app.db`. For Postgres: `postgresql://user:password@localhost:5432/dbname` (also run `pip install psycopg2-binary`). |
| `SECRET_KEY` | Secret used to sign JWTs. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`. Never commit this. |
| `ADMIN_SECRET_KEY` | A secret string. Anyone who includes this exact value as `admin_key` during registration becomes an admin. Keep it private; share only with people who should manage inventory. If unset, nobody can register as admin. |
| `ANTHROPIC_API_KEY` | API key for Anthropic's Claude API, used by the `/recommendations` endpoint. Get one at [console.anthropic.com](https://console.anthropic.com). Without it, recommendation requests for a non-empty cart return a 500. |

### 3. Run the app

```bash
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`, with interactive docs at `http://127.0.0.1:8000/docs`.

## API Overview

All request/response bodies are JSON unless noted otherwise.

### Auth (`/auth`)

| Method | Endpoint | Auth required | Description |
|---|---|---|---|
| POST | `/auth/` | No | Register a new user. Optional `admin_key` field grants the admin role if it matches `ADMIN_SECRET_KEY`. |
| POST | `/auth/token` | No | Log in (OAuth2 form data: `username`, `password`). Returns a JWT access token. |

### Products (`/products`)

| Method | Endpoint | Auth required | Description |
|---|---|---|---|
| GET | `/products` | No | List all products. |
| GET | `/products/{id}` | No | Get a single product. |
| POST | `/products` | Admin only | Create a new product. |
| PUT | `/products/{id}` | Admin only | Update an existing product. |
| DELETE | `/products/{id}` | Admin only | Delete a product. |

### Cart (`/cart`)

All cart routes require a valid JWT and only ever operate on the logged-in user's own cart.

| Method | Endpoint | Auth required | Description |
|---|---|---|---|
| POST | `/cart` | Any logged-in user | Add a product to your cart (or increase quantity if already present). Validates against available stock. |
| GET | `/cart` | Any logged-in user | View your own cart, joined with live product details. |
| PUT | `/cart/{item_id}` | Any logged-in user | Change the quantity of an item in your cart. |
| DELETE | `/cart/{item_id}` | Any logged-in user | Remove an item from your cart. |

### Checkout (`/checkout`)

`POST /checkout` requires a customer JWT and converts the current cart into a pending order. Send only the payment method; prices, stock, tax, and totals are read or calculated by the server. The initial sandbox pricing policy is ₹50 flat shipping, 18% GST on the item subtotal, ₹30 COD fee for COD orders, and no discount. Checkout snapshots product names and prices and does not yet process payment or change stock.

Example request body:

```json
{
  "payment_method": "CARD"
}
```

### Mock payment sandbox

The cart checkout continues to `/payment/sandbox/{order_id}` in the frontend. The backend sandbox endpoints require the same customer JWT:

| Method | Endpoint | Description |
|---|---|---|
| GET | `/payment/sandbox/{order_id}` | Read an owned order and its itemized test checkout summary. |
| POST | `/payment/sandbox/pay?order_id={order_id}` | Simulate payment for the order's selected method. |
| GET | `/orders/{order_id}` | Read order and payment status (owner or admin). |

Card test values: `4111 1111 1111 1111` succeeds; `4000 0000 0000 0002` declines; `4000 0000 0000 0069` simulates an expired card; `4000 0000 0000 0119` simulates a processing error. Use any cardholder name, a future `MM/YY` expiry, and a 3–4 digit CVV. Online test IDs are `success@test` and `fail@test`; netbanking test banks are SBI, HDFC, ICICI, and Axis. The sandbox banner makes clear that no money is charged.

Payment request bodies include only the fields for the selected method. For example:

```json
{
  "card_number": "4111111111111111",
  "cardholder_name": "Test Customer",
  "expiry": "12/30",
  "cvv": "123"
}
```

CVV and full card number are never persisted. On successful card/online payment, stock decrement, cart clearing, payment record, and order transition commit together. COD confirms the order without creating a gateway payment record.

### Recommendations (`/recommendations`)

| Method | Endpoint | Auth required | Description |
|---|---|---|---|
| GET | `/recommendations` | Any logged-in user | Suggests up to 5 products based on the user's current cart, using the Claude API. If the cart is empty, returns a small fallback list instead of calling the AI (no reason to spend an API call with nothing to reason about). |

### Misc

| Method | Endpoint | Auth required | Description |
|---|---|---|---|
| GET | `/` | No | Welcome message / health check. |
| GET | `/users/me` | Any logged-in user | Returns the decoded identity (username, id, role) from your token. |
| GET | `/admin/ping` | Admin only | Sanity-check route to confirm an admin token works. |

## Authentication Flow

1. Register via `POST /auth/` with a username, email, and password.
2. Log in via `POST /auth/token` (form data, not JSON — this follows the OAuth2 password flow) to receive an `access_token`.
3. Include the token on all subsequent requests: `Authorization: Bearer <access_token>`.

## Authorization Model

This project uses two layers of access control:

- **Authentication** (`get_current_user`) — confirms *who* is making the request, based on a valid JWT. Applied to any route that needs a logged-in user (e.g. cart routes).
- **Authorization** (`require_admin`) — confirms *what* the requester is allowed to do, based on their role. Applied only to inventory-management routes.
- **Ownership checks** — cart routes additionally filter every database query by the requesting user's own `id`, so authorization isn't just role-based but also scoped to "is this yours?"

## Known Issues / Things to Improve

- `Database_config/database_models.py` is a legacy duplicate of the `Product` model and isn't used anywhere; the actual model lives in `models.py`.
- There's no automated test suite yet.
- No pagination or filtering on `GET /products` yet.
- Orders and mock payment processing are implemented; replace the `PaymentProvider` implementation before integrating a real gateway.

## Roadmap

- [x] Mock payment sandbox and order lookup
- [ ] Pytest test suite
- [ ] Pagination and filtering for product listing
- [ ] Dockerfile + docker-compose for local setup
- [x] AI-based product recommendations
