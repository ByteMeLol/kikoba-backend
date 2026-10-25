from typing import List, Optional
from datetime import date
from sqlalchemy import String, Integer, Float, Numeric, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class Group(Base, TimestampMixin):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    share_value: Mapped[float] = mapped_column(Numeric(12, 2), default=5000.0, nullable=False)
    max_shares_per_meeting: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    interest_rate_monthly: Mapped[float] = mapped_column(Float, default=0.10, nullable=False)
    meeting_frequency: Mapped[str] = mapped_column(String(20), default="weekly", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    members: Mapped[List["GroupMember"]] = relationship("GroupMember", back_populates="group")
    cycles: Mapped[List["Cycle"]] = relationship("Cycle", back_populates="group")
    meetings: Mapped[List["Meeting"]] = relationship("Meeting", back_populates="group")


class GroupMember(Base, TimestampMixin):
    __tablename__ = "group_members"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default="member", nullable=False)  # chairperson, treasurer, secretary, member
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active, added_as_shadow

    # Relationships
    group: Mapped["Group"] = relationship("Group", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="group_memberships")
    transactions: Mapped[List["Transaction"]] = relationship("Transaction", back_populates="member")
    loans: Mapped[List["Loan"]] = relationship("Loan", back_populates="member")


class Cycle(Base, TimestampMixin):
    __tablename__ = "cycles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    cycle_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active, closed
    total_profit_distributed: Mapped[float] = mapped_column(Numeric(14, 2), default=0.0, nullable=False)
    dividend_per_share: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Relationships
    group: Mapped["Group"] = relationship("Group", back_populates="cycles")
