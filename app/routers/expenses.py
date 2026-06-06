from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import datetime, timezone

from app.database import get_db
from app.models.models import Expense, ExpenseSplit, User, Group, GroupMember, ExpenseComment
from app.middleware.auth_middleware import get_current_user
from app.services.split_service import calculate_splits
from app.services.balance_service import apply_expense_splits
from app.services.edit_log_service import write_log

router = APIRouter(tags=["expenses"])


class SplitParticipant(BaseModel):
    user_id: str
    amount: Optional[float] = None
    percentage: Optional[float] = None
    share_count: Optional[int] = None


class CreateExpenseRequest(BaseModel):
    group_id: str
    title: str
    amount: float
    currency: str = "USD"
    paid_by_user_id: str
    split_type: str
    participants: List[SplitParticipant]
    category: Optional[str] = None
    note: Optional[str] = None
    expense_date: Optional[str] = None


class CommentRequest(BaseModel):
    content: str


@router.post("/groups/{group_id}/expenses")
async def create_expense(group_id: str, body: CreateExpenseRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)

    participants = [p.model_dump() for p in body.participants]
    splits = calculate_splits(
        total=Decimal(str(body.amount)),
        split_type=body.split_type,
        paid_by_user_id=body.paid_by_user_id,
        participants=participants,
    )

    expense = Expense(
        group_id=group_id,
        title=body.title,
        amount=Decimal(str(body.amount)),
        currency=body.currency,
        paid_by_user_id=body.paid_by_user_id,
        created_by_user_id=user.id,
        split_type=body.split_type,
        category=body.category,
        note=body.note,
    )
    db.add(expense)
    await db.flush()

    for s in splits:
        split_row = ExpenseSplit(
            expense_id=expense.id,
            user_id=s["user_id"],
            amount=s["amount"],
            percentage=s.get("percentage"),
            share_count=s.get("share_count"),
        )
        db.add(split_row)

    await apply_expense_splits(db, group_id, body.paid_by_user_id, splits, body.currency, multiplier=1)
    await write_log(db, "expense", expense.id, user.id, "create", after={"title": body.title, "amount": str(body.amount), "currency": body.currency, "group_id": group_id})
    await db.commit()

    return {"success": True, "data": {"id": expense.id, "title": expense.title}}


@router.get("/expenses/{expense_id}")
async def get_expense(expense_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(select(Expense).where(Expense.id == expense_id))
    expense = result.scalar_one_or_none()
    if not expense or expense.deleted_at:
        raise HTTPException(404)

    splits_result = await db.execute(select(ExpenseSplit).where(ExpenseSplit.expense_id == expense_id))
    splits = []
    for s in splits_result.scalars().all():
        u = (await db.execute(select(User).where(User.id == s.user_id))).scalar_one_or_none()
        splits.append({
            "user_id": s.user_id,
            "user_name": u.full_name if u else "Unknown",
            "amount": float(s.amount),
            "percentage": float(s.percentage) if s.percentage else None,
            "share_count": s.share_count,
        })

    payer = (await db.execute(select(User).where(User.id == expense.paid_by_user_id))).scalar_one_or_none()
    return {"success": True, "data": {
        "id": expense.id, "title": expense.title, "amount": float(expense.amount),
        "currency": expense.currency, "split_type": expense.split_type,
        "paid_by_user_id": expense.paid_by_user_id,
        "paid_by_name": payer.full_name if payer else "Unknown",
        "category": expense.category, "note": expense.note,
        "expense_date": expense.expense_date.isoformat() if expense.expense_date else None,
        "splits": splits,
    }}


@router.put("/expenses/{expense_id}")
async def edit_expense(expense_id: str, body: CreateExpenseRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(select(Expense).where(Expense.id == expense_id))
    expense = result.scalar_one_or_none()
    if not expense or expense.deleted_at:
        raise HTTPException(404)

    # Get old splits to reverse balances
    old_splits_result = await db.execute(select(ExpenseSplit).where(ExpenseSplit.expense_id == expense_id))
    old_splits = [{"user_id": s.user_id, "amount": float(s.amount)} for s in old_splits_result.scalars().all()]

    before_snapshot = {"title": expense.title, "amount": str(expense.amount), "currency": expense.currency}

    # Reverse old balance impact
    await apply_expense_splits(db, expense.group_id, expense.paid_by_user_id, old_splits, expense.currency, multiplier=-1)

    # Delete old splits
    for s in (await db.execute(select(ExpenseSplit).where(ExpenseSplit.expense_id == expense_id))).scalars().all():
        await db.delete(s)

    # Calculate new splits
    participants = [p.model_dump() for p in body.participants]
    new_splits = calculate_splits(Decimal(str(body.amount)), body.split_type, body.paid_by_user_id, participants)

    expense.title = body.title
    expense.amount = Decimal(str(body.amount))
    expense.currency = body.currency
    expense.paid_by_user_id = body.paid_by_user_id
    expense.split_type = body.split_type
    expense.category = body.category
    expense.note = body.note

    for s in new_splits:
        db.add(ExpenseSplit(expense_id=expense.id, user_id=s["user_id"], amount=s["amount"],
                            percentage=s.get("percentage"), share_count=s.get("share_count")))

    await apply_expense_splits(db, expense.group_id, body.paid_by_user_id, new_splits, body.currency, multiplier=1)
    await write_log(db, "expense", expense.id, user.id, "update",
                    before=before_snapshot,
                    after={"title": body.title, "amount": str(body.amount), "currency": body.currency})
    await db.commit()
    return {"success": True, "data": {"id": expense.id}}


@router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(select(Expense).where(Expense.id == expense_id))
    expense = result.scalar_one_or_none()
    if not expense or expense.deleted_at:
        raise HTTPException(404)

    splits_result = await db.execute(select(ExpenseSplit).where(ExpenseSplit.expense_id == expense_id))
    splits = [{"user_id": s.user_id, "amount": float(s.amount)} for s in splits_result.scalars().all()]

    await apply_expense_splits(db, expense.group_id, expense.paid_by_user_id, splits, expense.currency, multiplier=-1)
    expense.deleted_at = datetime.now(timezone.utc)
    await write_log(db, "expense", expense.id, user.id, "delete",
                    before={"title": expense.title, "amount": str(expense.amount)})
    await db.commit()
    return {"success": True, "data": {"message": "Expense deleted"}}


@router.get("/expenses/{expense_id}/comments")
async def get_comments(expense_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(
        select(ExpenseComment).where(ExpenseComment.expense_id == expense_id).order_by(ExpenseComment.created_at)
    )
    data = []
    for c in result.scalars().all():
        u = (await db.execute(select(User).where(User.id == c.user_id))).scalar_one_or_none()
        data.append({"id": c.id, "content": c.content, "user_id": c.user_id,
                     "user_name": u.full_name if u else "Unknown",
                     "created_at": c.created_at.isoformat() if c.created_at else None})
    return {"success": True, "data": data}


@router.post("/expenses/{expense_id}/comments")
async def post_comment(expense_id: str, body: CommentRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    comment = ExpenseComment(expense_id=expense_id, user_id=user.id, content=body.content)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return {"success": True, "data": {"id": comment.id, "content": comment.content,
                                       "user_id": user.id, "user_name": user.full_name,
                                       "created_at": comment.created_at.isoformat()}}