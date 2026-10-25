from typing import List, Optional
from fastapi import APIRouter, status
from pydantic import BaseModel, Field

router = APIRouter()


class CreateGroupRequest(BaseModel):
    name: str = Field(..., examples=["Mavuno Women Group"])
    share_value: float = Field(..., examples=[5000.0])
    max_shares_per_meeting: int = Field(..., examples=[5])
    interest_rate_monthly: float = Field(..., examples=[0.10])
    meeting_frequency: str = Field(..., examples=["weekly"])


class CreateGroupResponse(BaseModel):
    group_id: int
    status: str = "active"


class AddMemberRequest(BaseModel):
    phone_number: str = Field(..., examples=["+255700000001"])
    role: str = Field(..., examples=["member"])
    full_name: str = Field(..., examples=["David"])


class AddMemberResponse(BaseModel):
    member_id: int
    status: str = "added_as_shadow"
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
async def create_group(payload: CreateGroupRequest):
    """
    Creates a new group, sets bylaws, and initializes the first cycle.
    The creator automatically becomes the Chairperson.
    """
    return CreateGroupResponse(group_id=101, status="active")


@router.post("/{group_id}/members", response_model=AddMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member_to_group(group_id: int, payload: AddMemberRequest):
    """
    Admin adds a user to the group. If not registered, creates a 'shadow profile'
    so they can be tracked on the ledger, and sends an SMS invite.
    """
    return AddMemberResponse(member_id=46, status="added_as_shadow", sms_sent=True)


@router.get("/{group_id}/members", response_model=List[MemberLedgerItem])
async def get_group_members_ledger(group_id: int):
    """
    Returns all members and their current standing (shares, social fund, loans).
    Used by Admins to view the master ledger.
    """
    return [
        MemberLedgerItem(
            member_id=45,
            user_id=45,
            full_name="Amina Juma",
            phone_number="+255700000000",
            role="chairperson",
            status="active",
            total_shares=15,
            social_fund_balance=10000.0,
            active_loans_count=1
        ),
        MemberLedgerItem(
            member_id=46,
            user_id=None,
            full_name="David",
            phone_number="+255700000001",
            role="member",
            status="added_as_shadow",
            total_shares=0,
            social_fund_balance=0.0,
            active_loans_count=0
        )
    ]
