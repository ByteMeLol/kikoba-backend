from typing import List, Optional
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    national_id: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    hashed_pin: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active, shadow, suspended
    kyc_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    group_memberships: Mapped[List["GroupMember"]] = relationship("GroupMember", back_populates="user")


class OTPVerification(Base, TimestampMixin):
    __tablename__ = "otp_verifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    reference_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    otp_code: Mapped[str] = mapped_column(String(10), nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
