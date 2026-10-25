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
async def test_webhook_endpoint(client: AsyncClient):
    # Webhook
    res = await client.post("/api/v1/webhooks/payments", json={
        "transaction_reference": "tx-8989",
        "status": "SUCCESS",
        "amount": 17000
    })
    assert res.status_code == 200
    assert res.json()["acknowledged"] is True
