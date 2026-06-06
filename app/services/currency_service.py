import httpx
from app.config import settings

_cache: dict = {}


async def get_rates(base: str = "USD") -> dict:
    if base in _cache:
        return _cache[base]
    url = f"https://v6.exchangerate-api.com/v6/{settings.EXCHANGE_RATE_API_KEY}/latest/{base}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=5.0)
        resp.raise_for_status()
        data = resp.json()
        rates = data.get("conversion_rates", {})
        _cache[base] = rates
        return rates


async def convert(amount: float, from_currency: str, to_currency: str) -> tuple[float, float]:
    """Returns (converted_amount, exchange_rate)."""
    if from_currency == to_currency:
        return amount, 1.0
    rates = await get_rates(from_currency)
    rate = rates.get(to_currency)
    if not rate:
        raise ValueError(f"Cannot convert {from_currency} to {to_currency}")
    return round(amount * rate, 2), rate