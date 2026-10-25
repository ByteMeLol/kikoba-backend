from datetime import date, datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_current_user, verify_group_membership
from app.db.session import get_db
from app.models.user import User
from app.models.group import Group, Cycle
from app.models.meeting import Meeting, Attendance, Fine

router = APIRouter()


class StartMeetingRequest(BaseModel):
    scheduled_date: date = Field(..., examples=["2026-09-07"])


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
async def start_meeting(
    group_id: int,
    payload: StartMeetingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Opens a new meeting ledger session. Admin permission required.
    """
    # Check group exists
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    # Verify admin permission
    await verify_group_membership(
        group_id=group_id,
        user=current_user,
        db=db,
        allowed_roles=["chairperson", "secretary", "treasurer"]
    )

    # Get active cycle
    cycle_stmt = select(Cycle).where(
        Cycle.group_id == group_id,
        Cycle.status == "active"
    ).order_by(Cycle.cycle_number.desc())
    active_cycle = (await db.execute(cycle_stmt)).scalars().first()

    meeting = Meeting(
        group_id=group_id,
        cycle_id=active_cycle.id if active_cycle else None,
        scheduled_date=payload.scheduled_date,
        status="in_progress"
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)

    return StartMeetingResponse(meeting_id=meeting.id, status=meeting.status)


@router.post("/{group_id}/meetings/{meeting_id}/attendance", response_model=RecordAttendanceResponse, status_code=status.HTTP_200_OK)
async def record_attendance(
    group_id: int,
    meeting_id: int,
    payload: RecordAttendanceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Admins mark attendance. Automatically generates fines for late or absent members
    based on group bylaws.
    """
    # Verify admin permission
    await verify_group_membership(
        group_id=group_id,
        user=current_user,
        db=db,
        allowed_roles=["chairperson", "secretary", "treasurer"]
    )

    # Verify meeting exists and belongs to this group
    stmt = select(Meeting).where(Meeting.id == meeting_id, Meeting.group_id == group_id)
    meeting = (await db.execute(stmt)).scalar_one_or_none()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found for this group"
        )

    fines_issued = 0

    # 1. Attendees (Present)
    for member_id in payload.attendees:
        att = Attendance(
            meeting_id=meeting.id,
            member_id=member_id,
            status="present"
        )
        db.add(att)

    # 2. Late Members (Fine assigned)
    for late_entry in payload.late:
        att = Attendance(
            meeting_id=meeting.id,
            member_id=late_entry.member_id,
            status="late"
        )
        db.add(att)

        fine = Fine(
            group_id=group_id,
            meeting_id=meeting.id,
            member_id=late_entry.member_id,
            amount=late_entry.fine_amount,
            reason="Late meeting attendance",
            is_paid=False
        )
        db.add(fine)
        fines_issued += 1

    # 3. Absent Members (Standard Fine assigned)
    for member_id in payload.absent:
        att = Attendance(
            meeting_id=meeting.id,
            member_id=member_id,
            status="absent"
        )
        db.add(att)

        fine = Fine(
            group_id=group_id,
            meeting_id=meeting.id,
            member_id=member_id,
            amount=2000.0,
            reason="Absent from meeting without leave",
            is_paid=False
        )
        db.add(fine)
        fines_issued += 1

    await db.commit()

    return RecordAttendanceResponse(
        message="Attendance recorded and fines generated successfully",
        fines_issued_count=fines_issued
    )
