from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timezone

from app.database import get_db
from app.models.models import Invite, User, Group, GroupMember
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/invites", tags=["invites"])


@router.get("/{token}")
async def validate_invite(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Invite).where(
            and_(Invite.token == token, Invite.status == "pending",
                 Invite.expires_at > datetime.now(timezone.utc))
        )
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(400, detail={"code": "INVALID_INVITE", "message": "Invite is invalid or expired"})

    group = (await db.execute(select(Group).where(Group.id == invite.group_id))).scalar_one_or_none()
    inviter = (await db.execute(select(User).where(User.id == invite.invited_by_user_id))).scalar_one_or_none()
    return {"success": True, "data": {
        "group_name": group.name if group else "Unknown",
        "inviter_name": inviter.full_name if inviter else "Unknown",
        "invited_email": invite.invited_email,
    }}


@router.post("/{token}/accept")
async def accept_invite(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(
        select(Invite).where(
            and_(Invite.token == token, Invite.status == "pending",
                 Invite.expires_at > datetime.now(timezone.utc))
        )
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(400, detail={"code": "INVALID_INVITE", "message": "Invite is invalid or expired"})

    existing = (await db.execute(
        select(GroupMember).where(and_(GroupMember.group_id == invite.group_id, GroupMember.user_id == user.id))
    )).scalar_one_or_none()

    if not existing:
        member = GroupMember(group_id=invite.group_id, user_id=user.id,
                              invited_by_user_id=invite.invited_by_user_id, role="member")
        db.add(member)

    invite.status = "accepted"
    invite.accepted_by_user_id = user.id
    invite.accepted_at = datetime.now(timezone.utc)
    await db.commit()
    return {"success": True, "data": {"group_id": invite.group_id}}