from typing import Optional
from sqlalchemy import String, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class SocialFundClaim(Base, TimestampMixin):
    __tablename__ = "social_fund_claims"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    member_id: Mapped[int] = mapped_column(ForeignKey("group_members.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # status: pending_group_approval, approved, rejected, disbursed
    status: Mapped[str] = mapped_column(String(30), default="pending_group_approval", nullable=False)
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
