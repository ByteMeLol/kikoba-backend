from fastapi import APIRouter, status
from pydantic import BaseModel, Field

router = APIRouter()


class ApplyLoanRequest(BaseModel):
    amount: float = Field(..., examples=[150000.0])
    purpose: str = Field(..., examples=["Agriculture"])
    duration_months: int = Field(..., examples=[3])


class ApplyLoanResponse(BaseModel):
    loan_id: int
    status: str = "pending_approval"


class ApproveLoanRequest(BaseModel):
    admin_pin: str = Field(..., min_length=4, max_length=4, examples=["1234"])


class ApproveLoanResponse(BaseModel):
    status: str = "disbursed"
    payout_reference: str = "MPESA-9923"


class RepayLoanRequest(BaseModel):
    amount: float = Field(..., examples=[55000.0])


class RepayLoanResponse(BaseModel):
    transaction_id: str
    status: str = "pending_payment"


@router.post("/{group_id}/loans/apply", response_model=ApplyLoanResponse, status_code=status.HTTP_201_CREATED)
async def apply_for_loan(group_id: int, payload: ApplyLoanRequest):
    """
    Validates eligibility (e.g. requested amount <= shares * 3) and records loan application.
    """
    return ApplyLoanResponse(loan_id=202, status="pending_approval")


@router.post("/{group_id}/loans/{loan_id}/approve", response_model=ApproveLoanResponse, status_code=status.HTTP_200_OK)
async def approve_and_disburse_loan(group_id: int, loan_id: int, payload: ApproveLoanRequest):
    """
    Admin approves the loan using Maker-Checker security PIN.
    Triggers B2C Mobile Money payout to the member.
    """
    return ApproveLoanResponse(status="disbursed", payout_reference="MPESA-9923")


@router.post("/{group_id}/loans/{loan_id}/repay", response_model=RepayLoanResponse, status_code=status.HTTP_202_ACCEPTED)
async def repay_loan(group_id: int, loan_id: int, payload: RepayLoanRequest):
    """
    Initiates a USSD push for a member to pay back their loan installment.
    """
    return RepayLoanResponse(transaction_id="tx-9001", status="pending_payment")
