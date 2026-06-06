from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.models import User, Balance, Group, GroupMember
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    preferred_currency: Optional[str] = None
    timezone: Optional[str] = None
    avatar_url: Optional[str] = None


@router.get("/me")
async def get_profile(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    return {"success": True, "data": {
        "id": user.id, "full_name": user.full_name, "email": user.email,
        "preferred_currency": user.preferred_currency, "avatar_url": user.avatar_url,
        "timezone": user.timezone,
    }}


@router.put("/me")
async def update_profile(body: UpdateProfileRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if body.full_name:
        user.full_name = body.full_name
    if body.preferred_currency:
        user.preferred_currency = body.preferred_currency
    if body.timezone:
        user.timezone = body.timezone
    if body.avatar_url:
        user.avatar_url = body.avatar_url
    await db.commit()
    return {"success": True, "data": {"message": "Profile updated"}}


@router.get("/me/balances")
async def cross_group_balances(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)

    result = await db.execute(
        select(Balance).where(
            or_(Balance.user_id_1 == user.id, Balance.user_id_2 == user.id)
        )
    )
    balances = result.scalars().all()

    net_total = 0.0
    details = []
    for b in balances:
        net = float(b.net_amount)
        # Positive net_amount = user_1 is owed by user_2
        if b.user_id_1 == user.id:
            my_net = net
        else:
            my_net = -net

        if abs(my_net) < 0.01:
            continue

        other_id = b.user_id_2 if b.user_id_1 == user.id else b.user_id_1
        other = (await db.execute(select(User).where(User.id == other_id))).scalar_one_or_none()
        group = (await db.execute(select(Group).where(Group.id == b.group_id))).scalar_one_or_none()

        net_total += my_net
        details.append({
            "group_id": b.group_id,
            "group_name": group.name if group else "Unknown",
            "other_user_id": other_id,
            "other_user_name": other.full_name if other else "Unknown",
            "net_amount": my_net,
            "currency": b.currency,
        })

    return {"success": True, "data": {"net_total": round(net_total, 2), "details": details}}