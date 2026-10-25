from fastapi import APIRouter, status
from pydantic import BaseModel, Field

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
async def register_user(payload: RegisterRequest):
    """
    Registers a new user or claims an existing shadow profile.
    If a shadow profile exists from an Admin invite, activates it and links the device/KYC.
    """
    return RegisterResponse(reference_id="mock-ref-uuid-1234")


@router.post("/request-otp", response_model=RequestOtpResponse, status_code=status.HTTP_200_OK)
async def request_otp(payload: RequestOtpRequest):
    """
    Checks if the user exists and is active, generates a 4-digit OTP, triggers SMS gateway.
    """
    return RequestOtpResponse(reference_id="mock-ref-uuid-1234")


@router.post("/verify", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def verify_otp(payload: VerifyOtpRequest):
    """
    Validates OTP against reference ID. Returns a JWT access token.
    """
    return TokenResponse(access_token="mock_jwt_access_token")
