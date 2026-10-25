import uuid
import random
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User, OTPVerification
from app.core.security import get_pin_hash, create_access_token
from app.services.sms import send_sms_notification

router = APIRouter()


class RegisterRequest(BaseModel):
    phone_number: str = Field(..., examples=["+255700000000"])
    full_name: str = Field(..., examples=["Amina Juma"])
    national_id: str = Field(..., examples=["19900101-12345-00001-2"])
    pin: str = Field(..., min_length=4, max_length=4, examples=["1234"])


class RegisterResponse(BaseModel):
    message: str = "User registered, OTP sent for verification"
    reference_id: str


class RequestOtpRequest(BaseModel):
    phone_number: str = Field(..., examples=["+255700000000"])


class RequestOtpResponse(BaseModel):
    message: str = "OTP sent successfully"
    reference_id: str


class VerifyOtpRequest(BaseModel):
    reference_id: str
    otp: str = Field(..., min_length=4, max_length=6, examples=["5678"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Registers a new user or claims an existing shadow profile.
    If a shadow profile exists from an Admin invite, activates it and links the device/KYC.
    Returns 409 Conflict if the phone number is already actively registered.
    """
    stmt = select(User).where(User.phone_number == payload.phone_number)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        if existing_user.status == "active" and existing_user.hashed_pin is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already registered"
            )
        # Claim shadow profile
        existing_user.full_name = payload.full_name
        existing_user.national_id = payload.national_id
        existing_user.hashed_pin = get_pin_hash(payload.pin)
        existing_user.status = "active"
        existing_user.kyc_verified = True
    else:
        new_user = User(
            phone_number=payload.phone_number,
            full_name=payload.full_name,
            national_id=payload.national_id,
            hashed_pin=get_pin_hash(payload.pin),
            status="active",
            kyc_verified=True
        )
        db.add(new_user)

    # Generate 4-digit OTP
    otp_code = f"{random.randint(1000, 9999)}"
    ref_id = str(uuid.uuid4())

    otp_record = OTPVerification(
        reference_id=ref_id,
        phone_number=payload.phone_number,
        otp_code=otp_code,
        is_used=False
    )
    db.add(otp_record)
    await db.commit()

    # Queue SMS OTP sending
    background_tasks.add_task(
        send_sms_notification,
        payload.phone_number,
        f"Your VICOBA verification code is: {otp_code}"
    )

    return RegisterResponse(reference_id=ref_id)


@router.post("/request-otp", response_model=RequestOtpResponse, status_code=status.HTTP_200_OK)
async def request_otp(
    payload: RequestOtpRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Checks if the user exists and is active.
    Generates a 4-digit OTP, triggers the SMS gateway, and returns reference ID.
    Returns 404 Not Found if user is not registered.
    """
    stmt = select(User).where(User.phone_number == payload.phone_number)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not registered"
        )

    otp_code = f"{random.randint(1000, 9999)}"
    ref_id = str(uuid.uuid4())

    otp_record = OTPVerification(
        reference_id=ref_id,
        phone_number=payload.phone_number,
        otp_code=otp_code,
        is_used=False
    )
    db.add(otp_record)
    await db.commit()

    background_tasks.add_task(
        send_sms_notification,
        payload.phone_number,
        f"Your VICOBA login OTP is: {otp_code}"
    )

    return RequestOtpResponse(reference_id=ref_id)


@router.post("/verify", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def verify_otp(
    payload: VerifyOtpRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Validates OTP against reference ID. Returns a JWT access token.
    """
    stmt = select(OTPVerification).where(
        OTPVerification.reference_id == payload.reference_id,
        OTPVerification.is_used == False
    )
    result = await db.execute(stmt)
    otp_record = result.scalar_one_or_none()

    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP reference"
        )

    if otp_record.otp_code != payload.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect OTP code"
        )

    otp_record.is_used = True

    # Fetch user
    user_stmt = select(User).where(User.phone_number == otp_record.phone_number)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated user account not found"
        )

    await db.commit()

    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token)
