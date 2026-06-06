from fastapi import Request, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.models.models import Session, User


async def get_current_user(request: Request, db: AsyncSession):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "INVALID_SESSION", "message": "Missing token"})

    token = auth_header.split(" ")[1]

    result = await db.execute(
        select(Session).where(
            and_(
                Session.session_id == token,
                Session.revoked_at.is_(None),
                Session.expires_at > datetime.now(timezone.utc)
            )
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=401, detail={"code": "INVALID_SESSION", "message": "Invalid or expired session"})

    result = await db.execute(select(User).where(User.id == session.user_id))
    user = result.scalar_one_or_none()
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=401, detail={"code": "INVALID_SESSION", "message": "User not found"})

    return user