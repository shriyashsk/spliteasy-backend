from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta

from app.database import get_db
from app.models.models import Group, GroupMember, User, Expense, Balance, Settlement, EditLog, Invite
from app.middleware.auth_middleware import get_current_user
from app.services.invite_service import send_invite_email
from app.services.auth_service import generate_token
from app.services.edit_log_service import write_log, derive_activity_text
from app.services.balance_service import get_group_balances

router = APIRouter(prefix="/groups", tags=["groups"])


class CreateGroupRequest(BaseModel):
    name: str
    category: Optional[str] = "other"
    description: Optional[str] = None
    currency: Optional[str] = "USD"
    default_split_preference: Optional[str] = "equal"


class InviteRequest(BaseModel):
    email: str


@router.get("")
async def list_groups(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(
        select(GroupMember).where(
            and_(GroupMember.user_id == user.id, GroupMember.removed_at.is_(None))
        )
    )
    memberships = result.scalars().all()
    groups = []
    for m in memberships:
        g_result = await db.execute(select(Group).where(Group.id == m.group_id))
        group = g_result.scalar_one_or_none()
        if group and not group.archived_at:
            groups.append({
                "id": group.id, "name": group.name, "category": group.category,
                "currency": group.currency, "default_split_preference": group.default_split_preference,
                "created_at": group.created_at.isoformat() if group.created_at else None,
            })
    return {"success": True, "data": groups}


@router.post("")
async def create_group(body: CreateGroupRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    group = Group(
        name=body.name, category=body.category, description=body.description,
        currency=body.currency, default_split_preference=body.default_split_preference,
        created_by_user_id=user.id,
    )
    db.add(group)
    await db.flush()

    member = GroupMember(group_id=group.id, user_id=user.id, role="admin")
    db.add(member)
    await db.commit()
    await db.refresh(group)
    return {"success": True, "data": {"id": group.id, "name": group.name}}


@router.get("/{group_id}")
async def get_group(group_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(404)

    members_result = await db.execute(
        select(GroupMember).where(and_(GroupMember.group_id == group_id, GroupMember.removed_at.is_(None)))
    )
    members = []
    for m in members_result.scalars().all():
        u_res = await db.execute(select(User).where(User.id == m.user_id))
        u = u_res.scalar_one_or_none()
        if u:
            members.append({"id": u.id, "full_name": u.full_name, "email": u.email,
                             "avatar_url": u.avatar_url, "role": m.role})

    return {"success": True, "data": {
        "id": group.id, "name": group.name, "category": group.category,
        "currency": group.currency, "description": group.description,
        "default_split_preference": group.default_split_preference,
        "created_by_user_id": group.created_by_user_id,
        "members": members,
    }}


@router.delete("/{group_id}/members/{user_id}")
async def remove_member(group_id: str, user_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    current_user = await get_current_user(request, db)
    admin_check = await db.execute(
        select(GroupMember).where(and_(GroupMember.group_id == group_id,
                                        GroupMember.user_id == current_user.id,
                                        GroupMember.role == "admin"))
    )
    if not admin_check.scalar_one_or_none():
        raise HTTPException(403, detail={"code": "FORBIDDEN", "message": "Only admin can remove members"})

    result = await db.execute(
        select(GroupMember).where(and_(GroupMember.group_id == group_id, GroupMember.user_id == user_id))
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(404)
    member.removed_at = datetime.now(timezone.utc)
    await write_log(db, "member", member.id, current_user.id, "delete",
                    before={"user_id": user_id, "group_id": group_id})
    await db.commit()
    return {"success": True, "data": {"message": "Member removed"}}


@router.get("/{group_id}/balances")
async def group_balances(group_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    balances = await get_group_balances(db, group_id)

    # Enrich with user names
    enriched = []
    for b in balances:
        u1 = (await db.execute(select(User).where(User.id == b["user_id_1"]))).scalar_one_or_none()
        u2 = (await db.execute(select(User).where(User.id == b["user_id_2"]))).scalar_one_or_none()
        enriched.append({
            **b,
            "user_1_name": u1.full_name if u1 else "Unknown",
            "user_2_name": u2.full_name if u2 else "Unknown",
        })
    return {"success": True, "data": enriched}


@router.get("/{group_id}/expenses")
async def list_expenses(group_id: str, request: Request, page: int = 1, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(
        select(Expense).where(
            and_(Expense.group_id == group_id, Expense.deleted_at.is_(None))
        ).order_by(Expense.created_at.desc()).limit(20).offset((page - 1) * 20)
    )
    expenses = result.scalars().all()
    data = []
    for e in expenses:
        payer = (await db.execute(select(User).where(User.id == e.paid_by_user_id))).scalar_one_or_none()
        data.append({
            "id": e.id, "title": e.title, "amount": float(e.amount),
            "currency": e.currency, "split_type": e.split_type,
            "paid_by_user_id": e.paid_by_user_id,
            "paid_by_name": payer.full_name if payer else "Unknown",
            "expense_date": e.expense_date.isoformat() if e.expense_date else None,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        })
    return {"success": True, "data": data}


@router.get("/{group_id}/settlements")
async def list_settlements(group_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(
        select(Settlement).where(
            and_(Settlement.group_id == group_id, Settlement.deleted_at.is_(None))
        ).order_by(Settlement.created_at.desc())
    )
    settlements = result.scalars().all()
    data = []
    for s in settlements:
        pb = (await db.execute(select(User).where(User.id == s.paid_by_user_id))).scalar_one_or_none()
        pt = (await db.execute(select(User).where(User.id == s.paid_to_user_id))).scalar_one_or_none()
        data.append({
            "id": s.id, "amount": float(s.amount), "currency": s.currency,
            "paid_by_name": pb.full_name if pb else "Unknown",
            "paid_to_name": pt.full_name if pt else "Unknown",
            "paid_by_user_id": s.paid_by_user_id,
            "paid_to_user_id": s.paid_to_user_id,
            "note": s.note, "status": s.status,
            "settlement_date": s.settlement_date.isoformat() if s.settlement_date else None,
        })
    return {"success": True, "data": data}


@router.get("/{group_id}/activity")
async def activity_feed(group_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(
        select(EditLog).where(
            EditLog.after_json.op("->>")(EditLog.after_json).contains(group_id) if False else
            EditLog.entity_id.in_(
                select(Expense.id).where(Expense.group_id == group_id).union(
                    select(Settlement.id).where(Settlement.group_id == group_id)
                )
            )
        ).order_by(EditLog.created_at.desc()).limit(50)
    )
    logs = result.scalars().all()
    data = []
    for log in logs:
        changer = (await db.execute(select(User).where(User.id == log.changed_by_user_id))).scalar_one_or_none()
        data.append({
            "id": log.id,
            "description": derive_activity_text(log),
            "changed_by": changer.full_name if changer else "Unknown",
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })
    return {"success": True, "data": data}


@router.post("/{group_id}/invites")
async def send_invite(group_id: str, body: InviteRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    group = (await db.execute(select(Group).where(Group.id == group_id))).scalar_one_or_none()
    if not group:
        raise HTTPException(404)

    token = generate_token(48)
    invite = Invite(
        token=token,
        group_id=group_id,
        invited_email=body.email,
        invited_by_user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    await db.commit()

    try:
        send_invite_email(body.email, user.full_name, group.name, token)
    except Exception as e:
        pass  # Don't fail the request if email fails

    return {"success": True, "data": {"message": f"Invite sent to {body.email}", "token": token}}