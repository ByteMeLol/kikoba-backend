import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.group import Group, GroupMember, Cycle
from app.models.meeting import Meeting, Fine
from app.models.transaction import Transaction
from app.models.loan import Loan
from app.core.security import create_access_token, get_pin_hash


@pytest_asyncio.fixture(scope="function")
async def setup_financial_env(db_session: AsyncSession):
    # Chairperson / Admin
    admin = User(
        phone_number="+255714000001",
        full_name="Amina Chairperson",
        hashed_pin=get_pin_hash("1234"),
        status="active",
        kyc_verified=True
    )
    # Borrower / Member
    member = User(
        phone_number="+255714000002",
        full_name="Juma Borrower",
        hashed_pin=get_pin_hash("5678"),
        status="active",
        kyc_verified=True
    )
    db_session.add_all([admin, member])
    await db_session.commit()
    await db_session.refresh(admin)
    await db_session.refresh(member)

    admin_token = create_access_token(subject=str(admin.id))
    member_token = create_access_token(subject=str(member.id))

    # Create Group: share value = 5000, max shares per meeting = 5, interest = 10%
    group = Group(
        name="Mavuno Financial Chama",
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

    cycle = Cycle(group_id=group.id, cycle_number=1, status="active")
    admin_mem = GroupMember(group_id=group.id, user_id=admin.id, role="chairperson", status="active")
    member_mem = GroupMember(group_id=group.id, user_id=member.id, role="member", status="active")
    db_session.add_all([cycle, admin_mem, member_mem])
    await db_session.commit()
    await db_session.refresh(cycle)
    await db_session.refresh(admin_mem)
    await db_session.refresh(member_mem)

    # Meeting
    from datetime import date
    meeting = Meeting(
        group_id=group.id,
        cycle_id=cycle.id,
        scheduled_date=date.today(),
        status="in_progress"
    )
    db_session.add(meeting)
    await db_session.commit()
    await db_session.refresh(meeting)

    return {
        "admin": admin,
        "admin_token": admin_token,
        "admin_mem": admin_mem,
        "member": member,
        "member_token": member_token,
        "member_mem": member_mem,
        "group": group,
        "cycle": cycle,
        "meeting": meeting
    }


@pytest.mark.asyncio
async def test_deposit_and_webhook_flow(client: AsyncClient, setup_financial_env, db_session: AsyncSession):
    env = setup_financial_env
    member_token = env["member_token"]
    group = env["group"]
    meeting = env["meeting"]
    member_mem = env["member_mem"]

    # 1. Try to buy 6 shares when max is 5 -> 400 Bad Request
    exceed_res = await client.post(
        f"/api/v1/groups/{group.id}/transactions/deposit",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "member_id": member_mem.id,
            "meeting_id": meeting.id,
            "shares_bought": 6,
            "social_fund_amount": 2000.0,
            "payment_method": "mobile_money"
        }
    )
    assert exceed_res.status_code == 400
    assert "exceeds maximum allowed" in exceed_res.json()["detail"]

    # 2. Buy valid 3 shares + 2000 social fund -> 202 Accepted
    deposit_res = await client.post(
        f"/api/v1/groups/{group.id}/transactions/deposit",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "member_id": member_mem.id,
            "meeting_id": meeting.id,
            "shares_bought": 3,
            "social_fund_amount": 2000.0,
            "payment_method": "mobile_money"
        }
    )
    assert deposit_res.status_code == 202
    tx_data = deposit_res.json()
    assert tx_data["status"] == "pending_payment"
    tx_ref = tx_data["transaction_id"]

    # 3. Simulate Payment Gateway Webhook Callback (Selcom / ClickPesa)
    webhook_res = await client.post(
        "/api/v1/webhooks/payments",
        json={
            "transaction_reference": tx_ref,
            "status": "SUCCESS",
            "amount": 17000.0
        }
    )
    assert webhook_res.status_code == 200
    assert webhook_res.json()["acknowledged"] is True

    # Verify transaction in DB is SUCCESS
    tx_stmt = select(Transaction).where(Transaction.reference_id == tx_ref)
    tx = (await db_session.execute(tx_stmt)).scalar_one()
    assert tx.status == "SUCCESS"
    assert tx.shares_bought == 3


@pytest.mark.asyncio
async def test_loan_lifecycle_and_repayment(client: AsyncClient, setup_financial_env, db_session: AsyncSession):
    env = setup_financial_env
    member_token = env["member_token"]
    admin_token = env["admin_token"]
    group = env["group"]
    member_mem = env["member_mem"]

    # Member owns 3 shares (3 * 5,000 = 15,000). Max eligible loan = 15,000 * 3 = 45,000 TZS.
    # Credit 3 shares to member in DB
    tx = Transaction(
        reference_id="tx-seed-1",
        group_id=group.id,
        member_id=member_mem.id,
        type="share_purchase",
        amount=15000.0,
        shares_bought=3,
        status="SUCCESS"
    )
    db_session.add(tx)
    await db_session.commit()

    # 1. Apply for loan exceeding 3x (e.g. 50,000 > 45,000) -> 400 Bad Request
    over_loan_res = await client.post(
        f"/api/v1/groups/{group.id}/loans/apply",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "amount": 50000.0,
            "purpose": "Agriculture seed purchase",
            "duration_months": 2
        }
    )
    assert over_loan_res.status_code == 400
    assert "exceeds 3x shares value" in over_loan_res.json()["detail"]

    # 2. Apply for eligible loan (40,000 <= 45,000) -> 201 Created
    apply_res = await client.post(
        f"/api/v1/groups/{group.id}/loans/apply",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "amount": 40000.0,
            "purpose": "Agriculture seed purchase",
            "duration_months": 2
        }
    )
    assert apply_res.status_code == 201
    loan_id = apply_res.json()["loan_id"]

    # 3. Approve loan with wrong admin PIN -> 400 Bad Request
    bad_pin_res = await client.post(
        f"/api/v1/groups/{group.id}/loans/{loan_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"admin_pin": "0000"}
    )
    assert bad_pin_res.status_code == 400
    assert "Invalid admin confirmation PIN" in bad_pin_res.json()["detail"]

    # 4. Approve loan with correct admin PIN (1234) -> 200 OK & disbursed
    approve_res = await client.post(
        f"/api/v1/groups/{group.id}/loans/{loan_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"admin_pin": "1234"}
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "disbursed"
    assert "payout_reference" in approve_res.json()

    # 5. Initiate loan repayment
    # Total due = 40,000 + (40,000 * 0.10 * 2) = 48,000 TZS.
    repay_res = await client.post(
        f"/api/v1/groups/{group.id}/loans/{loan_id}/repay",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"amount": 48000.0}
    )
    assert repay_res.status_code == 202
    repay_tx_ref = repay_res.json()["transaction_id"]

    # 6. Webhook confirms repayment
    wh_res = await client.post(
        "/api/v1/webhooks/payments",
        json={
            "transaction_reference": repay_tx_ref,
            "status": "SUCCESS",
            "amount": 48000.0
        }
    )
    assert wh_res.status_code == 200

    # Verify loan status in DB is now "repaid"
    loan_stmt = select(Loan).where(Loan.id == loan_id)
    loan = (await db_session.execute(loan_stmt)).scalar_one()
    assert loan.status == "repaid"
    assert float(loan.amount_repaid) == 48000.0


@pytest.mark.asyncio
async def test_social_fund_claim(client: AsyncClient, setup_financial_env):
    env = setup_financial_env
    member_token = env["member_token"]
    group = env["group"]

    res = await client.post(
        f"/api/v1/groups/{group.id}/social-fund/claim",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"amount": 50000.0, "reason": "Medical Emergency"}
    )
    assert res.status_code == 201
    assert res.json()["status"] == "pending_group_approval"
    assert "claim_id" in res.json()


@pytest.mark.asyncio
async def test_cycle_closure_and_dividend_distribution(client: AsyncClient, setup_financial_env, db_session: AsyncSession):
    env = setup_financial_env
    admin = env["admin"]
    admin_token = env["admin_token"]
    group = env["group"]
    cycle = env["cycle"]
    member_mem = env["member_mem"]
    admin_mem = env["admin_mem"]

    # Seed 10 shares to admin and 10 shares to member (total 20 shares)
    tx1 = Transaction(reference_id="tx-s1", group_id=group.id, member_id=admin_mem.id, type="share_purchase", amount=50000, shares_bought=10, status="SUCCESS")
    tx2 = Transaction(reference_id="tx-s2", group_id=group.id, member_id=member_mem.id, type="share_purchase", amount=50000, shares_bought=10, status="SUCCESS")
    # Seed fine (2,000) and interest profit (10,000)
    fine = Fine(group_id=group.id, member_id=member_mem.id, amount=2000.0, reason="Late", is_paid=True)
    loan = Loan(group_id=group.id, member_id=member_mem.id, amount=50000.0, purpose="Biz", duration_months=2, interest_rate=0.10, total_due=60000.0, amount_repaid=60000.0, status="repaid")
    db_session.add_all([tx1, tx2, fine, loan])
    await db_session.commit()

    # Close cycle with Maker-Checker multi-admin signatures and admin PIN
    close_res = await client.post(
        f"/api/v1/groups/{group.id}/cycles/{cycle.id}/close",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "admin_signatures": [admin.id],
            "confirmation_pin": "1234"
        }
    )
    assert close_res.status_code == 200
    data = close_res.json()
    assert data["status"] == "closed"
    # Total profit = 10,000 (interest) + 2,000 (fine) = 12,000 TZS.
    assert data["total_profit_distributed"] == 12000.0
    # Dividend per share = 12,000 / 20 shares = 600 TZS per share!
    assert data["dividend_per_share"] == 600.0
    assert data["member_payouts_initiated"] is True
