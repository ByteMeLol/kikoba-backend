import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User, OTPVerification
from app.core.config import settings


@pytest.mark.asyncio
async def test_register_and_verify_flow(client: AsyncClient, db_session: AsyncSession):
    # 1. Register new user
    res = await client.post("/api/v1/auth/register", json={
        "phone_number": "+255711000001",
        "full_name": "Amina Juma",
        "national_id": "19900101-12345-00001-2",
        "pin": "1234"
    })
    assert res.status_code == 201
    data = res.json()
    assert "reference_id" in data
    ref_id = data["reference_id"]

    # Verify user exists in database
    user_stmt = select(User).where(User.phone_number == "+255711000001")
    user = (await db_session.execute(user_stmt)).scalar_one_or_none()
    assert user is not None
    assert user.full_name == "Amina Juma"
    assert user.kyc_verified is True

    # Retrieve generated OTP and verify it is securely hashed in DB
    generated_otp = data["debug_otp"]
    otp_stmt = select(OTPVerification).where(OTPVerification.reference_id == ref_id)
    otp_record = (await db_session.execute(otp_stmt)).scalar_one_or_none()
    assert otp_record is not None
    assert otp_record.is_used is False
    # OTP in database must be hashed, not plain text!
    assert otp_record.otp_code != generated_otp
    assert otp_record.otp_code.startswith("$2")

    # 2. Test OTP Verification with wrong OTP -> 400
    bad_res = await client.post("/api/v1/auth/verify", json={
        "reference_id": ref_id,
        "otp": "0000"
    })
    assert bad_res.status_code == 400

    # 3. Test OTP Verification with correct OTP -> 200 & JWT
    verify_res = await client.post("/api/v1/auth/verify", json={
        "reference_id": ref_id,
        "otp": generated_otp
    })
    assert verify_res.status_code == 200
    token_data = verify_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    access_token = token_data["access_token"]

    # 4. Access digital passbook with token
    passbook_res = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert passbook_res.status_code == 200
    passbook_data = passbook_res.json()
    assert passbook_data["user_id"] == user.id
    assert passbook_data["name"] == "Amina Juma"
    assert passbook_data["kyc_verified"] is True


@pytest.mark.asyncio
async def test_duplicate_registration_returns_409(client: AsyncClient, db_session: AsyncSession):
    # Register first time
    await client.post("/api/v1/auth/register", json={
        "phone_number": "+255711000002",
        "full_name": "Bakari Ally",
        "national_id": "19920202-54321-00002-1",
        "pin": "4321"
    })

    # Register second time with same phone number
    res = await client.post("/api/v1/auth/register", json={
        "phone_number": "+255711000002",
        "full_name": "Bakari Ally Duplicate",
        "national_id": "19920202-54321-00002-1",
        "pin": "4321"
    })
    assert res.status_code == 409
    assert res.json()["detail"] == "Phone number already registered"


@pytest.mark.asyncio
async def test_claim_shadow_profile(client: AsyncClient, db_session: AsyncSession):
    # Setup shadow profile as created by a group admin
    shadow_user = User(
        phone_number="+255711000003",
        full_name="Shadow Member",
        status="shadow",
        hashed_pin=None,
        kyc_verified=False
    )
    db_session.add(shadow_user)
    await db_session.commit()

    # User self-registers to claim their profile
    res = await client.post("/api/v1/auth/register", json={
        "phone_number": "+255711000003",
        "full_name": "Claimed Member",
        "national_id": "19950505-11111-00003-3",
        "pin": "9999"
    })
    assert res.status_code == 201

    # Verify profile status updated
    user_stmt = select(User).where(User.phone_number == "+255711000003")
    user = (await db_session.execute(user_stmt)).scalar_one()
    assert user.status == "active"
    assert user.full_name == "Claimed Member"
    assert user.hashed_pin is not None
    assert user.kyc_verified is True


@pytest.mark.asyncio
async def test_request_otp_non_registered_user(client: AsyncClient):
    res = await client.post("/api/v1/auth/request-otp", json={
        "phone_number": "+255700999999"
    })
    assert res.status_code == 404
    assert res.json()["detail"] == "User is not registered"


@pytest.mark.asyncio
async def test_unauthorized_passbook_access(client: AsyncClient):
    res = await client.get("/api/v1/users/me")
    assert res.status_code == 401


def test_debug_otp_is_never_exposed_in_production():
    original_environment = settings.ENVIRONMENT
    original_debug = settings.DEBUG
    original_expose_debug_otp = settings.EXPOSE_DEBUG_OTP
    try:
        settings.ENVIRONMENT = "production"
        settings.DEBUG = True
        settings.EXPOSE_DEBUG_OTP = True

        from app.api.v1.endpoints.auth import get_debug_otp

        assert get_debug_otp("1234") is None
    finally:
        settings.ENVIRONMENT = original_environment
        settings.DEBUG = original_debug
        settings.EXPOSE_DEBUG_OTP = original_expose_debug_otp


def test_debug_otp_can_be_exposed_for_testers():
    original_environment = settings.ENVIRONMENT
    original_debug = settings.DEBUG
    original_expose_debug_otp = settings.EXPOSE_DEBUG_OTP
    try:
        settings.ENVIRONMENT = "testing"
        settings.DEBUG = False
        settings.EXPOSE_DEBUG_OTP = True

        from app.api.v1.endpoints.auth import get_debug_otp

        assert get_debug_otp("1234") == "1234"
    finally:
        settings.ENVIRONMENT = original_environment
        settings.DEBUG = original_debug
        settings.EXPOSE_DEBUG_OTP = original_expose_debug_otp
