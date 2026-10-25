from typing import List
from fastapi import APIRouter, status
from pydantic import BaseModel, Field

router = APIRouter()


class StartMeetingRequest(BaseModel):
    scheduled_date: str = Field(..., examples=["2026-09-07"])


class StartMeetingResponse(BaseModel):
    meeting_id: int
    status: str = "in_progress"


class LateMemberRecord(BaseModel):
    member_id: int
    fine_amount: float = Field(..., examples=[1000.0])


class RecordAttendanceRequest(BaseModel):
    attendees: List[int] = Field(..., examples=[[45, 46, 47]])
    late: List[LateMemberRecord] = Field(default=[], examples=[[{"member_id": 48, "fine_amount": 1000.0}]])
    absent: List[int] = Field(default=[], examples=[[49]])


class RecordAttendanceResponse(BaseModel):
    message: str = "Attendance recorded and fines generated successfully"
    fines_issued_count: int


@router.post("/{group_id}/meetings", response_model=StartMeetingResponse, status_code=status.HTTP_201_CREATED)
async def start_meeting(group_id: int, payload: StartMeetingRequest):
    """
    Opens a new meeting ledger session.
    """
    return StartMeetingResponse(meeting_id=12, status="in_progress")


@router.post("/{group_id}/meetings/{meeting_id}/attendance", response_model=RecordAttendanceResponse, status_code=status.HTTP_200_OK)
async def record_attendance(group_id: int, meeting_id: int, payload: RecordAttendanceRequest):
    """
    Admins mark attendance. Automatically generates fines for late or absent members
    based on group bylaws.
    """
    return RecordAttendanceResponse(
        message="Attendance recorded and fines generated successfully",
        fines_issued_count=len(payload.late) + len(payload.absent)
    )
