import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_root():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert data["docs"] == "/docs"


@pytest.mark.asyncio
async def test_all_spec_routes_exist():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Auth register
        res = await ac.post("/api/v1/auth/register", json={
            "phone_number": "+255700000000",
            "full_name": "Amina Juma",
            "national_id": "19900101-12345-00001-2",
            "pin": "1234"
        })
        assert res.status_code == 201
        assert "reference_id" in res.json()

        # Auth request-otp
        res = await ac.post("/api/v1/auth/request-otp", json={
            "phone_number": "+255700000000"
        })
        assert res.status_code == 200
        assert "reference_id" in res.json()

        # Auth verify
        res = await ac.post("/api/v1/auth/verify", json={
            "reference_id": "uuid-123",
            "otp": "5678"
        })
        assert res.status_code == 200
        assert "access_token" in res.json()

        # Users me
        res = await ac.get("/api/v1/users/me")
        assert res.status_code == 200
        assert res.json()["user_id"] == 45

        # Groups create
        res = await ac.post("/api/v1/groups", json={
            "name": "Mavuno Women Group",
            "share_value": 5000,
            "max_shares_per_meeting": 5,
            "interest_rate_monthly": 0.10,
            "meeting_frequency": "weekly"
        })
        assert res.status_code == 201

        # Webhook
        res = await ac.post("/api/v1/webhooks/payments", json={
            "transaction_reference": "tx-8989",
            "status": "SUCCESS",
            "amount": 17000
        })
        assert res.status_code == 200
        assert res.json()["acknowledged"] is True
