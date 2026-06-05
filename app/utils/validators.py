import re
from datetime import date


def validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_password(password: str) -> list[str]:
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    return errors


def validate_transaction_type(t: str) -> bool:
    return t in ("expense", "income")


def validate_date(date_str: str):
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


def validate_positive_number(value) -> bool:
    try:
        return float(value) > 0
    except (ValueError, TypeError):
        return False
