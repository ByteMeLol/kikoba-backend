import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.group import Group, GroupMember, Cycle
from app.models.meeting import Meeting, Fine
from app.core.security import create_access_token


@pytest_asyncio.fixture(scope="function")
async def setup_users_and_tokens(db_session: AsyncSession):
    # Admin User (Chairperson)
    admin = User(
        phone_number="+255712000001",
        full_name="Chairperson Mama",
        status="active",
        kyc_verified=True
    )
    # Regular Member User
    regular = User(
        phone_number="+255712000002",
        full_name="Regular Member",
        status="active",
        kyc_verified=True
    )
    db_session.add_all([admin, regular])
    await db_session.commit()
    await db_session.refresh(admin)
    await db_session.refresh(regular)

    admin_token = create_access_token(subject=str(admin.id))
    regular_token = create_access_token(subject=str(regular.id))

    return {
        "admin": admin,
        "admin_token": admin_token,
        "regular": regular,
        "regular_token": regular_token
    }


@pytest.mark.asyncio
async def test_create_group_and_verify_cycle(client: AsyncClient, setup_users_and_tokens, db_session: AsyncSession):
    admin_token = setup_users_and_tokens["admin_token"]
    admin = setup_users_and_tokens["admin"]

    res = await client.post(
        "/api/v1/groups",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Mavuno Women Group",
            "share_value": 5000.0,
            "max_shares_per_meeting": 5,
            "interest_rate_monthly": 0.10,
            "meeting_frequency": "weekly"
        }
    )
    assert res.status_code == 201
    data = res.json()
    assert "group_id" in data
    group_id = data["group_id"]

    # Verify Cycle 1 created
    cycle_stmt = select(Cycle).where(Cycle.group_id == group_id)
    cycle = (await db_session.execute(cycle_stmt)).scalar_one_or_none()
    assert cycle is not None
    assert cycle.cycle_number == 1
    assert cycle.status == "active"

    # Verify admin is Chairperson
    mem_stmt = select(GroupMember).where(
        GroupMember.group_id == group_id,
        GroupMember.user_id == admin.id
    )
    membership = (await db_session.execute(mem_stmt)).scalar_one_or_none()
    assert membership is not None
    assert membership.role == "chairperson"


@pytest.mark.asyncio
async def test_add_shadow_member_and_regular_member(client: AsyncClient, setup_users_and_tokens, db_session: AsyncSession):
    admin_token = setup_users_and_tokens["admin_token"]
    regular = setup_users_and_tokens["regular"]

    # Create Group first
    res = await client.post(
        "/api/v1/groups",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Upendo VICOBAS",
            "share_value": 10000.0,
            "max_shares_per_meeting": 10,
            "interest_rate_monthly": 0.05,
            "meeting_frequency": "monthly"
        }
    )
    group_id = res.json()["group_id"]

    # 1. Add unregistered phone -> should create shadow profile
    shadow_res = await client.post(
        f"/api/v1/groups/{group_id}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "phone_number": "+255712999888",
            "role": "member",
            "full_name": "Shadow David"
        }
    )
    assert shadow_res.status_code == 201
    assert shadow_res.json()["status"] == "added_as_shadow"
    assert shadow_res.json()["sms_sent"] is True

    # Check shadow user exists in DB
    shadow_user_stmt = select(User).where(User.phone_number == "+255712999888")
    shadow_user = (await db_session.execute(shadow_user_stmt)).scalar_one_or_none()
    assert shadow_user is not None
    assert shadow_user.status == "shadow"

    # 2. Add existing registered user (regular)
    reg_res = await client.post(
        f"/api/v1/groups/{group_id}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "phone_number": regular.phone_number,
            "role": "secretary",
            "full_name": regular.full_name
        }
    )
    assert reg_res.status_code == 201
    assert reg_res.json()["status"] == "active"

    # 3. Add same member again -> 409 Conflict
    dup_res = await client.post(
        f"/api/v1/groups/{group_id}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "phone_number": regular.phone_number,
            "role": "member",
            "full_name": regular.full_name
        }
    )
    assert dup_res.status_code == 409


@pytest.mark.asyncio
async def test_meeting_lifecycle_and_attendance_fines(client: AsyncClient, setup_users_and_tokens, db_session: AsyncSession):
    admin_token = setup_users_and_tokens["admin_token"]
    regular_token = setup_users_and_tokens["regular_token"]

    # Create Group
    res = await client.post(
        "/api/v1/groups",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Tumaini Group",
            "share_value": 5000.0,
            "max_shares_per_meeting": 5,
            "interest_rate_monthly": 0.10,
            "meeting_frequency": "weekly"
        }
    )
    group_id = res.json()["group_id"]

    # Add a member
    mem1_res = await client.post(
        f"/api/v1/groups/{group_id}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"phone_number": "+255713111222", "role": "member", "full_name": "Member One"}
    )
    m1_id = mem1_res.json()["member_id"]

    mem2_res = await client.post(
        f"/api/v1/groups/{group_id}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"phone_number": "+255713333444", "role": "member", "full_name": "Member Two"}
    )
    m2_id = mem2_res.json()["member_id"]

    # 1. Non-admin regular member tries to start meeting -> 403 Forbidden
    forbidden_res = await client.post(
        f"/api/v1/groups/{group_id}/meetings",
        headers={"Authorization": f"Bearer {regular_token}"},
        json={"scheduled_date": "2026-09-07"}
    )
    assert forbidden_res.status_code == 403

    # 2. Admin starts meeting -> 201 Created
    meeting_res = await client.post(
        f"/api/v1/groups/{group_id}/meetings",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"scheduled_date": "2026-09-07"}
    )
    assert meeting_res.status_code == 201
    meeting_id = meeting_res.json()["meeting_id"]

    # 3. Record attendance: m1 is late (fine: 1000), m2 is absent
    att_res = await client.post(
        f"/api/v1/groups/{group_id}/meetings/{meeting_id}/attendance",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "attendees": [],
            "late": [{"member_id": m1_id, "fine_amount": 1000.0}],
            "absent": [m2_id]
        }
    )
    assert att_res.status_code == 200
    assert att_res.json()["fines_issued_count"] == 2

    # Verify fines in database
    fines_stmt = select(Fine).where(Fine.meeting_id == meeting_id)
    fines = (await db_session.execute(fines_stmt)).scalars().all()
    assert len(fines) == 2
    fines_by_member = {f.member_id: float(f.amount) for f in fines}
    assert fines_by_member[m1_id] == 1000.0
    assert fines_by_member[m2_id] == 2000.0
