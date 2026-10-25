from typing import List, Optional
from datetime import date, datetime
from sqlalchemy import String, Integer, Numeric, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class Meeting(Base, TimestampMixin):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    cycle_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cycles.id"), nullable=True)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)  # scheduled, in_progress, completed

    # Relationships
    group: Mapped["Group"] = relationship("Group", back_populates="meetings")
    attendances: Mapped[List["Attendance"]] = relationship("Attendance", back_populates="meeting")
    fines: Mapped[List["Fine"]] = relationship("Fine", back_populates="meeting")


class Attendance(Base, TimestampMixin):
    __tablename__ = "attendances"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    member_id: Mapped[int] = mapped_column(ForeignKey("group_members.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # present, late, absent

    # Relationships
    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="attendances")


class Fine(Base, TimestampMixin):
    __tablename__ = "fines"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    meeting_id: Mapped[Optional[int]] = mapped_column(ForeignKey("meetings.id"), nullable=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("group_members.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    meeting: Mapped[Optional["Meeting"]] = relationship("Meeting", back_populates="fines")
