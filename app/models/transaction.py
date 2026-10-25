from typing import Optional
from sqlalchemy import String, Integer, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    reference_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    member_id: Mapped[int] = mapped_column(ForeignKey("group_members.id"), nullable=False)
    meeting_id: Mapped[Optional[int]] = mapped_column(ForeignKey("meetings.id"), nullable=True)
    
    # type: share_purchase, social_fund, loan_repayment, fine_payment
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    shares_bought: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    social_fund_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), default="mobile_money", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending_payment", nullable=False)  # pending_payment, SUCCESS, FAILED
    external_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    member: Mapped["GroupMember"] = relationship("GroupMember", back_populates="transactions")
