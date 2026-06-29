from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def parse_smart_score(value):
    """
    Điểm thông minh:
        1   -> 1
        10  -> 10
        35  -> 3.5
        325 -> 3.25
        05  -> 0.5
        075 -> 0.75
        100 -> 10
        3,5 -> 3.5
    """
    raw = str(value or "").strip().replace(",", ".")
    if not raw:
        return Decimal("0.00")

    try:
        if "." in raw:
            score = Decimal(raw)
        else:
            if not raw.isdigit():
                raise ValueError("Điểm không hợp lệ.")
            if raw == "10" or raw == "100":
                score = Decimal("10")
            elif len(raw) == 1:
                score = Decimal(raw)
            elif len(raw) == 2:
                score = Decimal(raw) / Decimal("10")
            elif len(raw) == 3:
                score = Decimal(raw) / Decimal("100")
            else:
                raise ValueError("Điểm không hợp lệ.")
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Điểm không hợp lệ.") from exc

    if score < 0 or score > 10:
        raise ValueError("Điểm phải nằm trong thang 0 đến 10.")

    return score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
