import validators


def test_valid_emails():
    assert validators.is_valid_email("priya@company.com")
    assert validators.is_valid_email("a.b+c@sub.example.co")


def test_invalid_emails():
    assert not validators.is_valid_email("not-an-email")
    assert not validators.is_valid_email("missing@domain")
    assert not validators.is_valid_email("")
    assert not validators.is_valid_email(None)


def test_employee_id_format():
    assert validators.is_valid_employee_id("EMP-1024")
    assert not validators.is_valid_employee_id("x")
    assert not validators.is_valid_employee_id("")


def test_password_strength():
    assert validators.password_strength_errors("short") != []
    assert validators.password_strength_errors("12345678") != []  # all digits
    assert validators.password_strength_errors("password") != []  # common
    assert validators.password_strength_errors("correcthorsebattery") == []


def test_validate_new_user_all_blank():
    errors = validators.validate_new_user("", "", "", lambda e: None)
    assert len(errors) == 3


def test_validate_new_user_duplicate_email():
    errors = validators.validate_new_user("EMP-1", "A B", "a@b.com", lambda e: {"id": 1})
    assert any("already exists" in e for e in errors)


def test_validate_new_user_ok():
    errors = validators.validate_new_user("EMP-1", "A B", "a@b.com", lambda e: None)
    assert errors == []
