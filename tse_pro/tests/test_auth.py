import pytest

streamlit = pytest.importorskip("streamlit", reason="requires `pip install -r requirements.txt`")
import auth


def test_hash_and_verify_roundtrip():
    h, salt = auth.hash_password("correcthorsebattery")
    assert auth.verify_password("correcthorsebattery", h, salt)


def test_wrong_password_rejected():
    h, salt = auth.hash_password("correcthorsebattery")
    assert not auth.verify_password("wrongpassword", h, salt)


def test_same_password_different_salt_different_hash():
    h1, s1 = auth.hash_password("samepassword")
    h2, s2 = auth.hash_password("samepassword")
    assert s1 != s2
    assert h1 != h2


def test_generate_password_has_letter_and_digit():
    for _ in range(20):
        pw = auth.generate_password()
        assert len(pw) == 10
        assert any(c.isalpha() for c in pw)
        assert any(c.isdigit() for c in pw)


def test_generate_password_avoids_ambiguous_chars():
    ambiguous = set("0O1lI")
    for _ in range(20):
        pw = auth.generate_password()
        assert not (set(pw) & ambiguous)
