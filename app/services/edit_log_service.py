from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import EditLog
import json


def _to_dict(obj) -> dict:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    result = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if hasattr(val, "isoformat"):
            val = val.isoformat()
        elif hasattr(val, "__float__"):
            val = float(val)
        result[col.name] = val
    return result


async def write_log(
    db: AsyncSession,
    entity_type: str,
    entity_id: str,
    changed_by_user_id: str,
    change_type: str,
    before=None,
    after=None,
):
    log = EditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        changed_by_user_id=changed_by_user_id,
        change_type=change_type,
        before_json=_to_dict(before),
        after_json=_to_dict(after),
    )
    db.add(log)


def derive_activity_text(log: EditLog) -> str:
    et = log.entity_type
    ct = log.change_type
    before = log.before_json or {}
    after = log.after_json or {}

    if et == "expense":
        if ct == "create":
            return f"Expense '{after.get('title')}' for {after.get('currency')} {after.get('amount')} was added"
        if ct == "update":
            parts = []
            if before.get("amount") != after.get("amount"):
                parts.append(f"amount changed from {before.get('amount')} to {after.get('amount')}")
            if before.get("title") != after.get("title"):
                parts.append(f"title changed from '{before.get('title')}' to '{after.get('title')}'")
            return f"Expense updated: {'; '.join(parts)}" if parts else "Expense updated"
        if ct == "delete":
            return f"Expense '{before.get('title')}' was deleted"
    if et == "settlement":
        if ct == "create":
            return f"Settlement of {after.get('currency')} {after.get('amount')} recorded"
        if ct == "delete":
            return "Settlement was reversed"
    if et == "member":
        if ct == "delete":
            return "A member was removed from the group"
    return f"{et} {ct}"