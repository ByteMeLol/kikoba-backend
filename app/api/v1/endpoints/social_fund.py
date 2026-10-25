from fastapi import APIRouter, status
from pydantic import BaseModel, Field

router = APIRouter()


class SocialFundClaimRequest(BaseModel):
    amount: float = Field(..., examples=[50000.0])
    reason: str = Field(..., examples=["Medical Emergency"])


class SocialFundClaimResponse(BaseModel):
    claim_id: int
    status: str = "pending_group_approval"


@router.post("/{group_id}/social-fund/claim", response_model=SocialFundClaimResponse, status_code=status.HTTP_201_CREATED)
async def request_social_fund_claim(group_id: int, payload: SocialFundClaimRequest):
    """
    Member requests emergency funds (e.g. medical, bereavement).
    """
    return SocialFundClaimResponse(claim_id=5, status="pending_group_approval")
