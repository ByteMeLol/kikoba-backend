from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, verify_group_membership
from app.db.session import get_db
from app.models.user import User
from app.models.group import Group, GroupMember, Cycle
from app.models.transaction import Transaction
from app.models.loan import Loan
from app.services.sms import send_sms_notification

router = APIRouter()


class CreateGroupRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=150, examples=["Mavuno Women Group"])
    share_value: float = Field(..., gt=0, examples=[5000.0])
    max_shares_per_meeting: int = Field(..., ge=1, le=50, examples=[5])
    interest_rate_monthly: float = Field(..., ge=0.0, le=0.50, examples=[0.10])
    meeting_frequency: str = Field(..., examples=["weekly"])


class CreateGroupResponse(BaseModel):
    group_id: int
    status: str = "active"


class ApproveGroupResponse(BaseModel):
    group_id: int
    status: str
    message: str


class AddMemberRequest(BaseModel):
    phone_number: str = Field(..., examples=["+255700000001"])
    role: str = Field(default="member", examples=["member"])
    full_name: str = Field(..., examples=["David"])


class AddMemberResponse(BaseModel):
    member_id: int
    status: str
    sms_sent: bool = True


class MemberLedgerItem(BaseModel):
    member_id: int
    user_id: Optional[int]
    full_name: str
    phone_number: str
    role: str
    status: str
    total_shares: int
    social_fund_balance: float
    active_loans_count: int


@router.post("", response_model=CreateGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: CreateGroupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new VICOBA group, sets bylaws, and initializes the first cycle.
    Enforces pre-activation checks (KYC verification, valid bylaws, duplicate protection).
    The creator automatically becomes the Chairperson.
    """
    # 1. Pre-activation check: Creator must have completed KYC
    if not current_user.kyc_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Creator must complete KYC verification before creating a group"
        )

    # 2. Pre-activation check: Meeting frequency validation
    frequency = payload.meeting_frequency.strip().lower()
    if frequency not in ["weekly", "biweekly", "monthly"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meeting frequency must be one of: weekly, biweekly, monthly"
        )

    # 3. Pre-activation check: Share value minimum check
    if payload.share_value < 500.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Share value must be at least 500 TZS"
        )

    # 4. Pre-activation check: Duplicate group name check
    cleaned_name = payload.name.strip()
    dup_stmt = select(Group).where(
        func.lower(Group.name) == cleaned_name.lower(),
        Group.status == "active"
    )
    dup_res = await db.execute(dup_stmt)
    if dup_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active group with this name already exists"
        )

    new_group = Group(
        name=cleaned_name,
        share_value=payload.share_value,
        max_shares_per_meeting=payload.max_shares_per_meeting,
        interest_rate_monthly=payload.interest_rate_monthly,
        meeting_frequency=frequency,
        created_by_id=current_user.id,
        status="active"
    )
    db.add(new_group)
    await db.flush()

    # Initialize Cycle 1
    cycle_1 = Cycle(
        group_id=new_group.id,
        cycle_number=1,
        status="active"
    )
    db.add(cycle_1)

    # Assign creator as Chairperson
    chairperson_member = GroupMember(
        group_id=new_group.id,
        user_id=current_user.id,
        role="chairperson",
        status="active"
    )
    db.add(chairperson_member)
    await db.commit()

    return CreateGroupResponse(group_id=new_group.id, status=new_group.status)


@router.post("/{group_id}/approve", response_model=ApproveGroupResponse, status_code=status.HTTP_200_OK)
async def approve_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Administrative approval endpoint to approve and activate a pending group.
    Requires Super Admin or Chairperson permissions.
    """
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    if not current_user.is_superuser:
        await verify_group_membership(
            group_id=group_id,
            user=current_user,
            db=db,
            allowed_roles=["chairperson"]
        )

    if group.status == "active":
        return ApproveGroupResponse(
            group_id=group.id,
            status=group.status,
            message="Group is already active"
        )

    group.status = "active"
    await db.commit()
    return ApproveGroupResponse(
        group_id=group.id,
        status=group.status,
        message="Group successfully approved and activated"
    )


@router.post("/{group_id}/members", response_model=AddMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member_to_group(
    group_id: int,
    payload: AddMemberRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Admin adds a user to the group. If not registered, creates a 'shadow profile'
    so they can be tracked on the ledger, and sends an SMS invite.
    """
    # Verify group exists
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    # Verify caller is an admin
    await verify_group_membership(
        group_id=group_id,
        user=current_user,
        db=db,
        allowed_roles=["chairperson", "secretary", "treasurer"]
    )

    # Check if user already exists
    user_stmt = select(User).where(User.phone_number == payload.phone_number)
    user_res = await db.execute(user_stmt)
    target_user = user_res.scalar_one_or_none()

    member_status = "active"
    sms_needed = False

    if not target_user:
        # Create shadow profile
        target_user = User(
            phone_number=payload.phone_number,
            full_name=payload.full_name,
            status="shadow",
            kyc_verified=False,
            hashed_pin=None
        )
        db.add(target_user)
        await db.flush()
        member_status = "added_as_shadow"
        sms_needed = True
    else:
        # Check if already a member of this group
        existing_mem_stmt = select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == target_user.id
        )
        existing_mem = (await db.execute(existing_mem_stmt)).scalar_one_or_none()
        if existing_mem:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this group"
            )

        if target_user.status == "shadow":
            member_status = "added_as_shadow"
            sms_needed = True

    # Add to group members
    group_member = GroupMember(
        group_id=group_id,
        user_id=target_user.id,
        role=payload.role.lower(),
        status=member_status
    )
    db.add(group_member)
    await db.commit()
    await db.refresh(group_member)

    if sms_needed:
        background_tasks.add_task(
            send_sms_notification,
            payload.phone_number,
            f"Hello {payload.full_name}, you have been added to {group.name} on VICOBA. Download the app to track your shares."
        )

    return AddMemberResponse(
        member_id=group_member.id,
        status=member_status,
        sms_sent=sms_needed
    )


@router.get("/{group_id}/members", response_model=List[MemberLedgerItem])
async def get_group_members_ledger(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all members and their current standing (shares, social fund, loans).
    Used by Admins to view the master ledger.
    """
    # Verify group exists
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    # Verify caller is a member
    await verify_group_membership(group_id=group_id, user=current_user, db=db)

    # Fetch all members
    stmt = (
        select(GroupMember)
        .options(selectinload(GroupMember.user))
        .where(GroupMember.group_id == group_id)
    )
    result = await db.execute(stmt)
    members = result.scalars().all()

    ledger: List[MemberLedgerItem] = []

    for m in members:
        # Sum shares and social fund
        tx_stmt = select(
            func.coalesce(func.sum(Transaction.shares_bought), 0),
            func.coalesce(func.sum(Transaction.social_fund_amount), 0.0)
        ).where(
            Transaction.member_id == m.id,
            Transaction.status == "SUCCESS"
        )
        tx_res = await db.execute(tx_stmt)
        total_shares, social_fund = tx_res.one()

        # Count active loans
        loan_stmt = select(func.count(Loan.id)).where(
            Loan.member_id == m.id,
            Loan.status == "disbursed"
        )
        active_loans_count = (await db.execute(loan_stmt)).scalar() or 0

        ledger.append(
            MemberLedgerItem(
                member_id=m.id,
                user_id=m.user_id if m.user and m.user.status == "active" else None,
                full_name=m.user.full_name if m.user else "Unknown",
                phone_number=m.user.phone_number if m.user else "",
                role=m.role,
                status=m.status,
                total_shares=int(total_shares),
                social_fund_balance=float(social_fund),
                active_loans_count=int(active_loans_count)
            )
        )

    return ledger
