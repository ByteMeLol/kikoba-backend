from typing import Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.group import GroupMember

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Validates Bearer JWT token from Authorization header and returns the authenticated User.
    Raises 401 Unauthorized if token is missing, invalid, or expired.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token"
        )

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject"
        )

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token subject"
        )

    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active"
        )

    return user


async def verify_group_membership(
    group_id: int,
    user: User,
    db: AsyncSession,
    allowed_roles: Optional[List[str]] = None
) -> GroupMember:
    """
    Verifies that the user is a member of the specified group and optionally checks
    that their role is among allowed_roles (e.g. ['chairperson', 'secretary', 'treasurer']).
    """
    stmt = select(GroupMember).where(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user.id
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group"
        )

    if allowed_roles and membership.role.lower() not in [r.lower() for r in allowed_roles]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Action requires one of the following roles: {', '.join(allowed_roles)}"
        )

    return membership
