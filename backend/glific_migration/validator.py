from email_validator import validate_email, EmailNotValidError


def validate_required_fields(row, fields):
    missing = [f for f in fields if f not in row or not row[f].strip()]
    return missing


def validate_email_format(email: str):
    try:
        validate_email(email, check_deliverability=False)
        return True, None
    except EmailNotValidError as e:
        return False, str(e)


def validate_password(password: str):
    return len(password) >= 8
