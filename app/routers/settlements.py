from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime, timezone

from app.database import get_db
from app.models.models import Settlement, Balance, GroupMember
from app.middleware.auth_middleware import get_current_user
from app.services.balance_service import apply_settlement
from app.services.edit_log_service import write_log

router = APIRouter(tags=["settlements"])


class CreateSettlementRequest(BaseModel):
    paid_by_user_id: str
    paid_to_user_id: str
    amount: float
    currency: str = "USD"
    note: Optional[str] = None
    upi_transaction_ref: Optional[str] = None


@router.post("/groups/{group_id}/settlements")
async def create_settlement(group_id: str, body: CreateSettlementRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)

    settlement = Settlement(
        group_id=group_id,
        paid_by_user_id=body.paid_by_user_id,
        paid_to_user_id=body.paid_to_user_id,
        amount=Decimal(str(body.amount)),
        currency=body.currency,
        note=body.note,
        upi_transaction_ref=body.upi_transaction_ref,
    )
    db.add(settlement)
    await db.flush()

    await apply_settlement(db, group_id, body.paid_by_user_id, body.paid_to_user_id,
                            Decimal(str(body.amount)), body.currency, multiplier=1)
    await write_log(db, "settlement", settlement.id, user.id, "create",
                    after={"amount": str(body.amount), "currency": body.currency, "group_id": group_id})
    await db.commit()
    return {"success": True, "data": {"id": settlement.id}}


@router.post("/settlements/{settlement_id}/reverse")
async def reverse_settlement(settlement_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(select(Settlement).where(Settlement.id == settlement_id))
    settlement = result.scalar_one_or_none()
    if not settlement or settlement.deleted_at:
        raise HTTPException(404)

    settlement.deleted_at = datetime.now(timezone.utc)
    settlement.status = "reversed"
    await apply_settlement(db, settlement.group_id, settlement.paid_by_user_id, settlement.paid_to_user_id,
                            Decimal(str(settlement.amount)), settlement.currency, multiplier=-1)
    await write_log(db, "settlement", settlement.id, user.id, "delete",
                    before={"amount": str(settlement.amount)})
    await db.commit()
    return {"success": True, "data": {"message": "Settlement reversed"}}