from decimal import Decimal
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.models import Balance


def _ordered_pair(uid1: str, uid2: str):
    """Always return (smaller_uuid, larger_uuid) — enforces uniqueness convention."""
    if uid1 < uid2:
        return uid1, uid2
    return uid2, uid1


def _sign_for_user1(payer_id: str, participant_id: str, uid1: str) -> int:
    """
    Convention: positive net_amount means user_1 is owed BY user_2.
    When the payer pays, the participant owes the payer.
    If payer == uid1: payer is user_1, participant owes payer → positive.
    If payer == uid2: payer is user_2, participant owes user_2 → negative from user_1's perspective.
    """
    if payer_id == uid1:
        return 1
    return -1


async def apply_expense_splits(
    db: AsyncSession,
    group_id: str,
    paid_by_user_id: str,
    splits: List[Dict],
    currency: str,
    multiplier: int = 1,
):
    """
    multiplier=1 to add an expense, -1 to reverse it.
    splits: [{ user_id, amount }]
    Skips the payer (they paid, they don't owe themselves).
    """
    for split in splits:
        participant_id = split["user_id"]
        if participant_id == paid_by_user_id:
            continue

        amount = Decimal(str(split["amount"])) * multiplier
        uid1, uid2 = _ordered_pair(paid_by_user_id, participant_id)
        sign = _sign_for_user1(paid_by_user_id, participant_id, uid1)
        delta = amount * sign

        result = await db.execute(
            select(Balance).where(
                and_(
                    Balance.group_id == group_id,
                    Balance.user_id_1 == uid1,
                    Balance.user_id_2 == uid2,
                )
            )
        )
        balance = result.scalar_one_or_none()
        if balance:
            balance.net_amount = Decimal(str(balance.net_amount)) + delta
        else:
            balance = Balance(
                group_id=group_id,
                user_id_1=uid1,
                user_id_2=uid2,
                net_amount=delta,
                currency=currency,
            )
            db.add(balance)


async def apply_settlement(
    db: AsyncSession,
    group_id: str,
    paid_by_user_id: str,
    paid_to_user_id: str,
    amount: Decimal,
    currency: str,
    multiplier: int = 1,
):
    """Settlement: person who owed pays. Reduces the balance."""
    uid1, uid2 = _ordered_pair(paid_by_user_id, paid_to_user_id)
    sign = _sign_for_user1(paid_to_user_id, paid_by_user_id, uid1)
    delta = Decimal(str(amount)) * sign * multiplier

    result = await db.execute(
        select(Balance).where(
            and_(
                Balance.group_id == group_id,
                Balance.user_id_1 == uid1,
                Balance.user_id_2 == uid2,
            )
        )
    )
    balance = result.scalar_one_or_none()
    if balance:
        balance.net_amount = Decimal(str(balance.net_amount)) + delta
    else:
        balance = Balance(
            group_id=group_id,
            user_id_1=uid1,
            user_id_2=uid2,
            net_amount=delta,
            currency=currency,
        )
        db.add(balance)


async def get_group_balances(db: AsyncSession, group_id: str) -> List[Dict]:
    result = await db.execute(
        select(Balance).where(Balance.group_id == group_id)
    )
    balances = result.scalars().all()
    out = []
    for b in balances:
        if b.net_amount != 0:
            out.append({
                "user_id_1": b.user_id_1,
                "user_id_2": b.user_id_2,
                "net_amount": float(b.net_amount),
                "currency": b.currency,
            })
    return out