from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    users,
    groups,
    meetings,
    transactions,
    loans,
    social_fund,
    cycles,
    webhooks
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Registration"])
api_router.include_router(users.router, prefix="/users", tags=["Users & Digital Passbook"])
api_router.include_router(groups.router, prefix="/groups", tags=["Group (Chama) Management"])
api_router.include_router(meetings.router, prefix="/groups", tags=["Meeting & Attendance"])
api_router.include_router(transactions.router, prefix="/groups", tags=["Fund Mobilization (Deposits)"])
api_router.include_router(loans.router, prefix="/groups", tags=["Credit Allocation (Loans & Repayments)"])
api_router.include_router(social_fund.router, prefix="/groups", tags=["Social Fund (Insurance Claims)"])
api_router.include_router(cycles.router, prefix="/groups", tags=["Cycle Closure (Share-out)"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks & Callbacks"])
