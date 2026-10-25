import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert data["docs"] == "/docs"


@pytest.mark.asyncio
async def test_spec_routes_stubs(client: AsyncClient):
    # Groups create
    res = await client.post("/api/v1/groups", json={
        "name": "Mavuno Women Group",
        "share_value": 5000,
        "max_shares_per_meeting": 5,
        "interest_rate_monthly": 0.10,
        "meeting_frequency": "weekly"
    })
    assert res.status_code == 201

    # Webhook
    res = await client.post("/api/v1/webhooks/payments", json={
        "transaction_reference": "tx-8989",
        "status": "SUCCESS",
        "amount": 17000
    })
    assert res.status_code == 200
    assert res.json()["acknowledged"] is True
