from decimal import Decimal, ROUND_DOWN
from typing import List, Dict


def calculate_splits(
    total: Decimal,
    split_type: str,
    paid_by_user_id: str,
    participants: List[Dict],
) -> List[Dict]:
    """
    Returns list of dicts: { user_id, amount, percentage, share_count }
    Rounding remainder always goes to the payer.
    participants format per split type:
      equal:      [{ user_id }]
      unequal:    [{ user_id, amount }]
      percentage: [{ user_id, percentage }]
      shares:     [{ user_id, share_count }]
    """
    total = Decimal(str(total))
    results = []

    if split_type == "equal":
        n = len(participants)
        base = (total / n).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        remainder = total - (base * n)
        for p in participants:
            amt = base + remainder if p["user_id"] == paid_by_user_id else base
            results.append({
                "user_id": p["user_id"],
                "amount": amt,
                "percentage": None,
                "share_count": None,
            })

    elif split_type == "unequal":
        given_total = sum(Decimal(str(p["amount"])) for p in participants)
        if abs(given_total - total) > Decimal("0.02"):
            raise ValueError(f"Unequal split amounts sum to {given_total}, expected {total}")
        for p in participants:
            results.append({
                "user_id": p["user_id"],
                "amount": Decimal(str(p["amount"])).quantize(Decimal("0.01")),
                "percentage": None,
                "share_count": None,
            })

    elif split_type == "percentage":
        pct_total = sum(Decimal(str(p["percentage"])) for p in participants)
        if abs(pct_total - Decimal("100")) > Decimal("0.01"):
            raise ValueError(f"Percentages sum to {pct_total}, must be 100")
        calculated = []
        running = Decimal("0")
        for p in participants:
            pct = Decimal(str(p["percentage"]))
            amt = (total * pct / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            running += amt
            calculated.append({
                "user_id": p["user_id"],
                "amount": amt,
                "percentage": pct,
                "share_count": None,
            })
        remainder = total - running
        for c in calculated:
            if c["user_id"] == paid_by_user_id:
                c["amount"] += remainder
                break
        else:
            calculated[0]["amount"] += remainder
        results = calculated

    elif split_type == "shares":
        total_shares = sum(int(p["share_count"]) for p in participants)
        if total_shares == 0:
            raise ValueError("Total shares cannot be zero")
        calculated = []
        running = Decimal("0")
        for p in participants:
            sc = int(p["share_count"])
            amt = (total * Decimal(sc) / Decimal(total_shares)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            running += amt
            calculated.append({
                "user_id": p["user_id"],
                "amount": amt,
                "percentage": None,
                "share_count": sc,
            })
        remainder = total - running
        for c in calculated:
            if c["user_id"] == paid_by_user_id:
                c["amount"] += remainder
                break
        else:
            calculated[0]["amount"] += remainder
        results = calculated

    else:
        raise ValueError(f"Unknown split_type: {split_type}")

    return results