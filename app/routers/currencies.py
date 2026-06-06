from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.currency_service import get_rates
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/currencies", tags=["currencies"])


@router.get("/rates")
async def exchange_rates(base: str = "USD", request: Request = None, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    rates = await get_rates(base)
    return {"success": True, "data": {"base": base, "rates": rates}}