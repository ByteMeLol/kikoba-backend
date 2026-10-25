from typing import Optional
from datetime import date, datetime
from sqlalchemy import String, Integer, Float, Numeric, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class Loan(Base, TimestampMixin):
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    member_id: Mapped[int] = mapped_column(ForeignKey("group_members.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_months: Mapped[int] = mapped_column(Integer, nullable=False)
    interest_rate: Mapped[float] = mapped_column(Float, nullable=False)
    total_due: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    amount_repaid: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    
    # status: pending_approval, disbursed, repaid, defaulted
    status: Mapped[str] = mapped_column(String(30), default="pending_approval", nullable=False)
    payout_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    disbursed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Relationships
    member: Mapped["GroupMember"] = relationship("GroupMember", back_populates="loans")
