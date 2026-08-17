"""Auth: PBKDF2-SHA256 password hashing (stdlib only) + Streamlit session helpers."""
import hashlib
import datetime
import secrets
import string
import streamlit as st
import config
import db
from logger import get_logger

log = get_logger(__name__)


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), config.PBKDF2_ITERATIONS).hex()
    return digest, salt


def verify_password(password, stored_hash, salt):
    digest, _ = hash_password(password, salt)
    return secrets.compare_digest(digest, stored_hash)


def generate_password(length=10):
    """Generates a password guaranteed to include a letter and a digit, avoiding ambiguous chars."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isalpha() for c in pw) and any(c.isdigit() for c in pw):
            return pw


def login(email, password):
    """Returns (user, error_message). Applies a lockout after repeated failed attempts."""
    email = (email or "").strip().lower()
    if not email or not password:
        return None, "Enter both email and password."

    since = (datetime.datetime.now() - datetime.timedelta(minutes=config.LOGIN_LOCKOUT_MINUTES)).isoformat(timespec="seconds")
    recent_failures = db.recent_failed_attempts(email, since)
    if recent_failures >= config.MAX_LOGIN_ATTEMPTS:
        log.warning("Login blocked (lockout) for %s", email)
        return None, (f"Too many failed attempts. Try again in a few minutes "
                       f"(locks out after {config.MAX_LOGIN_ATTEMPTS} tries).")

    user = db.get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"], user["salt"]):
        db.record_login_attempt(email, success=False)
        log.info("Failed login attempt for %s", email)
        return None, "Incorrect email or password."

    db.record_login_attempt(email, success=True)
    db.update_last_login(user["id"])
    st.session_state["user"] = user
    log.info("User %s (%s) logged in", user["email"], user["role"])
    return user, None


def logout():
    u = st.session_state.pop("user", None)
    if u:
        log.info("User %s logged out", u["email"])


def current_user():
    return st.session_state.get("user")


def is_logged_in():
    return current_user() is not None


def is_admin():
    u = current_user()
    return bool(u and u["role"] == "admin")


def require_login():
    if not is_logged_in():
        st.warning("Please log in from the Home page first.")
        st.stop()


def require_admin():
    require_login()
    if not is_admin():
        st.error("This page is for admins only.")
        st.stop()
