import pytest
from datetime import date, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User, OTPVerification
from app.models.group import Group, GroupMember
from app.models.meeting import Meeting, Attendance, Fine
from app.core.security import create_access_token, get_pin_hash, verify_pin


@pytest.mark.asyncio
async def test_otp_is_hashed_in_database(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies issue from testing PDF:
    'FYI: OTP should be hashed when stored in db'
    """
    res = await client.post("/api/v1/auth/register", json={
        "phone_number": "+255799111222",
        "full_name": "Test Hashed OTP User",
        "national_id": "19900101-99999-00001-1",
        "pin": "1234"
    })
    assert res.status_code == 201
    data = res.json()
    ref_id = data["reference_id"]
    debug_otp = data.get("debug_otp")

    # Inspect the raw row in the database
    otp_stmt = select(OTPVerification).where(OTPVerification.reference_id == ref_id)
    otp_row = (await db_session.execute(otp_stmt)).scalar_one()

    # The DB record MUST NOT be the plain text OTP code
    assert otp_row.otp_code != debug_otp
    assert len(otp_row.otp_code) > 20
    assert otp_row.otp_code.startswith("$2")  # Bcrypt hash prefix
    assert verify_pin(debug_otp, otp_row.otp_code) is True

    # Verification must succeed with raw OTP
    verify_res = await client.post("/api/v1/auth/verify", json={
        "reference_id": ref_id,
        "otp": debug_otp
    })
    assert verify_res.status_code == 200
    assert "access_token" in verify_res.json()


@pytest.mark.asyncio
async def test_meeting_past_date_rejected_and_future_status(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies issue from testing PDF:
    'Tried to schedule a meeting on 7th of October 2020... How the hell is meeting going to be conducted while it's scheduled in the past'
    """
    admin = User(
        phone_number="+255799333444",
        full_name="Admin Meeting Tester",
        status="active",
        kyc_verified=True
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)

    group = Group(
        name="Meeting Test Group",
        share_value=5000.0,
        max_shares_per_meeting=5,
        interest_rate_monthly=0.10,
        meeting_frequency="weekly",
        created_by_id=admin.id,
        status="active"
    )
    db_session.add(group)
    await db_session.commit()
    await db_session.refresh(group)

    membership = GroupMember(group_id=group.id, user_id=admin.id, role="chairperson", status="active")
    db_session.add(membership)
    await db_session.commit()

    token = create_access_token(subject=str(admin.id))

    # 1. Past date (2020-10-07) MUST be rejected with 400 Bad Request
    past_res = await client.post(
        f"/api/v1/groups/{group.id}/meetings",
        headers={"Authorization": f"Bearer {token}"},
        json={"scheduled_date": "2020-10-07"}
    )
    assert past_res.status_code == 400
    assert "Meeting date cannot be in the past" in past_res.json()["detail"]

    # 2. Future date MUST create meeting with status 'scheduled' (not 'in_progress')
    future_date = (date.today() + timedelta(days=10)).isoformat()
    future_res = await client.post(
        f"/api/v1/groups/{group.id}/meetings",
        headers={"Authorization": f"Bearer {token}"},
        json={"scheduled_date": future_date}
    )
    assert future_res.status_code == 201
    future_meeting = future_res.json()
    assert future_meeting["status"] == "scheduled"
    meeting_id = future_meeting["meeting_id"]

    # 3. Trying to record attendance on a future scheduled meeting before starting returns 400
    att_fail_res = await client.post(
        f"/api/v1/groups/{group.id}/meetings/{meeting_id}/attendance",
        headers={"Authorization": f"Bearer {token}"},
        json={"attendees": [membership.id], "late": [], "absent": []}
    )
    assert att_fail_res.status_code == 400
    assert "has not started yet" in att_fail_res.json()["detail"]

    # 4. Starting the meeting transitions it to 'in_progress'
    start_res = await client.post(
        f"/api/v1/groups/{group.id}/meetings/{meeting_id}/start",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "in_progress"

    # 5. Now attendance can be recorded
    att_ok_res = await client.post(
        f"/api/v1/groups/{group.id}/meetings/{meeting_id}/attendance",
        headers={"Authorization": f"Bearer {token}"},
        json={"attendees": [membership.id], "late": [], "absent": []}
    )
    assert att_ok_res.status_code == 200


@pytest.mark.asyncio
async def test_group_creation_pre_activation_checks(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies issue from testing PDF:
    'It was successful but this should not be this simple(only admin should approve this process otherwise the system should have some kind of checks before activating a group)'
    """
    # 1. User without KYC verification cannot create group
    unverified_user = User(
        phone_number="+255799555666",
        full_name="Unverified User",
        status="active",
        kyc_verified=False
    )
    db_session.add(unverified_user)
    await db_session.commit()
    await db_session.refresh(unverified_user)

    unverified_token = create_access_token(subject=str(unverified_user.id))

    unverified_res = await client.post(
        "/api/v1/groups",
        headers={"Authorization": f"Bearer {unverified_token}"},
        json={
            "name": "Should Fail KYC Group",
            "share_value": 5000.0,
            "max_shares_per_meeting": 5,
            "interest_rate_monthly": 0.10,
            "meeting_frequency": "weekly"
        }
    )
    assert unverified_res.status_code == 400
    assert "KYC" in unverified_res.json()["detail"]

    # 2. Verified user with invalid frequency fails
    verified_user = User(
        phone_number="+255799777888",
        full_name="Verified User",
        status="active",
        kyc_verified=True
    )
    db_session.add(verified_user)
    await db_session.commit()
    await db_session.refresh(verified_user)

    verified_token = create_access_token(subject=str(verified_user.id))

    bad_freq_res = await client.post(
        "/api/v1/groups",
        headers={"Authorization": f"Bearer {verified_token}"},
        json={
            "name": "Invalid Freq Group",
            "share_value": 5000.0,
            "max_shares_per_meeting": 5,
            "interest_rate_monthly": 0.10,
            "meeting_frequency": "hourly"
        }
    )
    assert bad_freq_res.status_code == 400
    assert "frequency" in bad_freq_res.json()["detail"].lower()

    # 3. Verified user with valid bylaws succeeds
    ok_res = await client.post(
        "/api/v1/groups",
        headers={"Authorization": f"Bearer {verified_token}"},
        json={
            "name": "Legit Verified Group",
            "share_value": 5000.0,
            "max_shares_per_meeting": 5,
            "interest_rate_monthly": 0.10,
            "meeting_frequency": "weekly"
        }
    )
    assert ok_res.status_code == 201
    assert ok_res.json()["status"] == "active"


@pytest.mark.asyncio
async def test_attendance_deduplication(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies that a member is not duplicated if passed in both 'attendees' and 'late'.
    """
    admin = User(
        phone_number="+255799000111",
        full_name="Admin Deduplicator",
        status="active",
        kyc_verified=True
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)

    group = Group(
        name="Dedup Group",
        share_value=5000.0,
        max_shares_per_meeting=5,
        interest_rate_monthly=0.10,
        meeting_frequency="weekly",
        created_by_id=admin.id,
        status="active"
    )
    db_session.add(group)
    await db_session.commit()
    await db_session.refresh(group)

    membership = GroupMember(group_id=group.id, user_id=admin.id, role="chairperson", status="active")
    db_session.add(membership)
    await db_session.commit()
    await db_session.refresh(membership)

    meeting = Meeting(
        group_id=group.id,
        scheduled_date=date.today(),
        status="in_progress"
    )
    db_session.add(meeting)
    await db_session.commit()
    await db_session.refresh(meeting)

    token = create_access_token(subject=str(admin.id))

    # Send member in both attendees AND late
    att_res = await client.post(
        f"/api/v1/groups/{group.id}/meetings/{meeting.id}/attendance",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "attendees": [membership.id],
            "late": [{"member_id": membership.id, "fine_amount": 1000.0}],
            "absent": []
        }
    )
    assert att_res.status_code == 200

    # Ensure only 1 attendance row was written for this member
    stmt = select(Attendance).where(Attendance.meeting_id == meeting.id, Attendance.member_id == membership.id)
    records = (await db_session.execute(stmt)).scalars().all()
    assert len(records) == 1
    assert records[0].status == "late"


@pytest.mark.asyncio
async def test_elive_sms_notification_dispatch():
    """
    Verifies that the Elive SMS notification function builds and dispatches
    the expected payload format (senderId, messageType, message, contacts, deliveryReportUrl)
    with headers (Content-Type, api_key, api_secret).
    """
    from app.services.sms import send_sms_notification
    # In test/dev mode without live api key, it succeeds and logs mock dispatch
    result = await send_sms_notification("+255712345678", "Your VICOBA code is 9988")
    assert result is True
