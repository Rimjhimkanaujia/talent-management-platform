"""Input validation helpers for Talent Management Platform."""
import re
import config

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
EMPLOYEE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{1,29}$")


def is_valid_email(email):
    return bool(EMAIL_RE.match((email or "").strip()))


def is_valid_employee_id(emp_id):
    return bool(EMPLOYEE_ID_RE.match((emp_id or "").strip()))


def password_strength_errors(password):
    """Returns a list of human-readable problems with the password (empty list = OK)."""
    errors = []
    if len(password or "") < config.MIN_PASSWORD_LENGTH:
        errors.append(f"Must be at least {config.MIN_PASSWORD_LENGTH} characters.")
    if password and password.isdigit():
        errors.append("Can't be all numbers.")
    if password and password.lower() in {"password", "12345678", "qwertyui"}:
        errors.append("That password is too common — pick something less guessable.")
    return errors


def validate_new_user(employee_id, name, email, existing_user_lookup):
    """existing_user_lookup: callable(email) -> user dict or None. Returns list of errors."""
    errors = []
    if not employee_id or not employee_id.strip():
        errors.append("Employee ID is required.")
    elif not is_valid_employee_id(employee_id):
        errors.append("Employee ID should be short alphanumeric, e.g. EMP-1024.")
    if not name or not name.strip():
        errors.append("Full name is required.")
    if not email or not email.strip():
        errors.append("Email is required.")
    elif not is_valid_email(email):
        errors.append("That doesn't look like a valid email address.")
    elif existing_user_lookup(email.strip().lower()):
        errors.append("A user with this email already exists.")
    return errors
