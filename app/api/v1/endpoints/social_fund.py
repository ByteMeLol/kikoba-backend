from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, verify_group_membership
from app.db.session import get_db
from app.models.user import User
from app.models.group import Group
from app.models.social_fund import SocialFundClaim

router = APIRouter()


class SocialFundClaimRequest(BaseModel):
    amount: float = Field(..., examples=[50000.0])
    reason: str = Field(..., examples=["Medical Emergency"])


class SocialFundClaimResponse(BaseModel):
    claim_id: int
    status: str = "pending_group_approval"


@router.post("/{group_id}/social-fund/claim", response_model=SocialFundClaimResponse, status_code=status.HTTP_201_CREATED)
async def request_social_fund_claim(
    group_id: int,
    payload: SocialFundClaimRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Member requests emergency funds (e.g. medical, bereavement).
    Submits claim for group official approval.
    """
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    membership = await verify_group_membership(group_id=group_id, user=current_user, db=db)

    claim = SocialFundClaim(
        group_id=group_id,
        member_id=membership.id,
        amount=payload.amount,
        reason=payload.reason,
        status="pending_group_approval"
    )
    db.add(claim)
    await db.commit()
    await db.refresh(claim)

    return SocialFundClaimResponse(claim_id=claim.id, status=claim.status)
