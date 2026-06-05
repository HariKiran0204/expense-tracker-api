"""
Integration tests for auth and transaction flows.
Run with: pytest tests/ -v
"""
import pytest
import json
from app import create_app, db


class TestConfig:
    SECRET_KEY = "test-secret"
    JWT_SECRET_KEY = "test-jwt-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = True
    JWT_ACCESS_TOKEN_EXPIRES = False  # Tokens don't expire during tests
    JWT_REFRESH_TOKEN_EXPIRES = False
    RATELIMIT_ENABLED = False
    RATELIMIT_STORAGE_URI = "memory://"


@pytest.fixture
def app():
    app = create_app(TestConfig)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(client):
    """Register + login, return auth headers."""
    client.post("/api/auth/register", json={
        "name": "Test User", "email": "test@example.com", "password": "password123"
    })
    resp = client.post("/api/auth/login", json={
        "email": "test@example.com", "password": "password123"
    })
    token = resp.get_json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Auth Tests ────────────────────────────────────────────────

class TestAuth:
    def test_register_success(self, client):
        r = client.post("/api/auth/register", json={
            "name": "Alice", "email": "alice@test.com", "password": "password123"
        })
        assert r.status_code == 201
        data = r.get_json()
        assert data["success"] is True
        assert "access_token" in data["data"]

    def test_register_duplicate_email(self, client):
        payload = {"name": "Bob", "email": "bob@test.com", "password": "password123"}
        client.post("/api/auth/register", json=payload)
        r = client.post("/api/auth/register", json=payload)
        assert r.status_code == 400

    def test_register_validation(self, client):
        r = client.post("/api/auth/register", json={"name": "", "email": "bad", "password": "short"})
        assert r.status_code == 400
        errors = r.get_json()["errors"]
        assert "email" in errors
        assert "password" in errors

    def test_login_success(self, client):
        client.post("/api/auth/register", json={
            "name": "Carol", "email": "carol@test.com", "password": "password123"
        })
        r = client.post("/api/auth/login", json={"email": "carol@test.com", "password": "password123"})
        assert r.status_code == 200
        assert "access_token" in r.get_json()["data"]

    def test_login_wrong_password(self, client):
        client.post("/api/auth/register", json={
            "name": "Dave", "email": "dave@test.com", "password": "password123"
        })
        r = client.post("/api/auth/login", json={"email": "dave@test.com", "password": "wrongpass"})
        assert r.status_code == 401

    def test_protected_route_without_token(self, client):
        r = client.get("/api/users/me")
        assert r.status_code == 401

    def test_logout(self, client, auth_headers):
        r = client.post("/api/auth/logout", headers=auth_headers)
        assert r.status_code == 200
        # Token should now be revoked
        r2 = client.get("/api/users/me", headers=auth_headers)
        assert r2.status_code == 401


# ── User Tests ────────────────────────────────────────────────

class TestUsers:
    def test_get_profile(self, client, auth_headers):
        r = client.get("/api/users/me", headers=auth_headers)
        assert r.status_code == 200
        assert r.get_json()["data"]["email"] == "test@example.com"

    def test_update_profile(self, client, auth_headers):
        r = client.put("/api/users/me", headers=auth_headers, json={"name": "Updated Name"})
        assert r.status_code == 200
        assert r.get_json()["data"]["name"] == "Updated Name"

    def test_change_password(self, client, auth_headers):
        r = client.put("/api/users/me/password", headers=auth_headers, json={
            "current_password": "password123", "new_password": "newpassword456"
        })
        assert r.status_code == 200

    def test_change_password_wrong_current(self, client, auth_headers):
        r = client.put("/api/users/me/password", headers=auth_headers, json={
            "current_password": "wrongpass", "new_password": "newpassword456"
        })
        assert r.status_code == 400


# ── Transaction Tests ─────────────────────────────────────────

class TestTransactions:
    def _get_category_id(self, client, auth_headers):
        cats = client.get("/api/categories", headers=auth_headers).get_json()["data"]
        return cats[0]["id"]

    def test_create_transaction(self, client, auth_headers):
        cat_id = self._get_category_id(client, auth_headers)
        r = client.post("/api/transactions", headers=auth_headers, json={
            "type": "expense", "amount": 49.99, "category_id": cat_id, "date": "2024-06-01"
        })
        assert r.status_code == 201
        data = r.get_json()["data"]
        assert data["amount"] == 49.99
        assert data["type"] == "expense"

    def test_create_transaction_validation(self, client, auth_headers):
        r = client.post("/api/transactions", headers=auth_headers, json={
            "type": "invalid", "amount": -10, "category_id": 999, "date": "not-a-date"
        })
        assert r.status_code == 400
        errors = r.get_json()["errors"]
        assert "type" in errors

    def test_list_transactions(self, client, auth_headers):
        cat_id = self._get_category_id(client, auth_headers)
        for i in range(3):
            client.post("/api/transactions", headers=auth_headers, json={
                "type": "expense", "amount": 10 + i, "category_id": cat_id, "date": "2024-06-01"
            })
        r = client.get("/api/transactions", headers=auth_headers)
        assert r.status_code == 200
        assert len(r.get_json()["data"]) >= 3

    def test_get_transaction(self, client, auth_headers):
        cat_id = self._get_category_id(client, auth_headers)
        create_r = client.post("/api/transactions", headers=auth_headers, json={
            "type": "income", "amount": 1000, "category_id": cat_id, "date": "2024-06-01"
        })
        txn_id = create_r.get_json()["data"]["id"]
        r = client.get(f"/api/transactions/{txn_id}", headers=auth_headers)
        assert r.status_code == 200
        assert r.get_json()["data"]["id"] == txn_id

    def test_cannot_access_other_users_transaction(self, client, auth_headers):
        # Register second user
        client.post("/api/auth/register", json={
            "name": "Eve", "email": "eve@test.com", "password": "password123"
        })
        resp2 = client.post("/api/auth/login", json={"email": "eve@test.com", "password": "password123"})
        headers2 = {"Authorization": "Bearer " + resp2.get_json()["data"]["access_token"]}

        # Create transaction as user 2
        cat_id = self._get_category_id(client, headers2)
        txn_r = client.post("/api/transactions", headers=headers2, json={
            "type": "expense", "amount": 50, "category_id": cat_id, "date": "2024-06-01"
        })
        txn_id = txn_r.get_json()["data"]["id"]

        # Try to fetch as user 1
        r = client.get(f"/api/transactions/{txn_id}", headers=auth_headers)
        assert r.status_code == 404

    def test_update_transaction(self, client, auth_headers):
        cat_id = self._get_category_id(client, auth_headers)
        txn_r = client.post("/api/transactions", headers=auth_headers, json={
            "type": "expense", "amount": 100, "category_id": cat_id, "date": "2024-06-01"
        })
        txn_id = txn_r.get_json()["data"]["id"]
        r = client.put(f"/api/transactions/{txn_id}", headers=auth_headers, json={"amount": 200})
        assert r.status_code == 200
        assert r.get_json()["data"]["amount"] == 200.0

    def test_delete_transaction(self, client, auth_headers):
        cat_id = self._get_category_id(client, auth_headers)
        txn_r = client.post("/api/transactions", headers=auth_headers, json={
            "type": "expense", "amount": 30, "category_id": cat_id, "date": "2024-06-01"
        })
        txn_id = txn_r.get_json()["data"]["id"]
        r = client.delete(f"/api/transactions/{txn_id}", headers=auth_headers)
        assert r.status_code == 200
        # Confirm deleted
        r2 = client.get(f"/api/transactions/{txn_id}", headers=auth_headers)
        assert r2.status_code == 404

    def test_filter_by_type(self, client, auth_headers):
        r = client.get("/api/transactions?type=expense", headers=auth_headers)
        assert r.status_code == 200

    def test_pagination(self, client, auth_headers):
        r = client.get("/api/transactions?page=1&per_page=5", headers=auth_headers)
        assert r.status_code == 200
        meta = r.get_json()["meta"]
        assert "total" in meta
        assert meta["per_page"] == 5


# ── Analytics Tests ───────────────────────────────────────────

class TestAnalytics:
    def test_summary(self, client, auth_headers):
        r = client.get("/api/analytics/summary", headers=auth_headers)
        assert r.status_code == 200
        data = r.get_json()["data"]
        assert "total_income" in data
        assert "total_expenses" in data
        assert "net_balance" in data

    def test_breakdown(self, client, auth_headers):
        r = client.get("/api/analytics/breakdown?type=expense", headers=auth_headers)
        assert r.status_code == 200

    def test_monthly(self, client, auth_headers):
        r = client.get("/api/analytics/monthly?months=3", headers=auth_headers)
        assert r.status_code == 200
        data = r.get_json()["data"]
        assert len(data["data"]) == 3
