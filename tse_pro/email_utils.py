"""Sends account-credential emails (new user registration, password reset) via SMTP.

Nothing is hardcoded: the SMTP server, sender address, and login URL all come from
config.py (which reads them from environment variables / .env). If SMTP isn't
configured, callers should fall back to showing the password on-screen once.
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config
from logger import get_logger

log = get_logger(__name__)


def _html_template(name, email, password, heading, intro):
    return f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:520px;margin:0 auto;
                border:1px solid #E0DFDC;border-radius:12px;overflow:hidden;">
      <div style="background:#0A66C2;padding:22px 24px;">
        <div style="color:#fff;font-weight:700;font-size:1.15rem;">{config.APP_NAME}</div>
        <div style="color:#d7e7fb;font-size:0.8rem;">{config.APP_FULL_NAME}</div>
      </div>
      <div style="padding:24px;">
        <h2 style="margin-top:0;color:#1a1a1a;font-size:1.1rem;">{heading}</h2>
        <p style="color:#444;font-size:0.95rem;line-height:1.5;">{intro}</p>
        <div style="background:#f5f7fa;border:1px solid #E0DFDC;border-radius:10px;
                    padding:16px 18px;margin:18px 0;">
          <div style="font-size:0.9rem;color:#333;margin-bottom:6px;">
            <strong>Username:</strong> {email}
          </div>
          <div style="font-size:0.9rem;color:#333;">
            <strong>Password:</strong> {password}
          </div>
        </div>
        <p style="color:#c0392b;font-size:0.82rem;">
          * For security reasons, we highly recommend changing your password immediately
          after your first login.
        </p>
        <a href="{config.APP_LOGIN_URL}"
           style="display:inline-block;margin-top:8px;background:#0A66C2;color:#fff;
                  text-decoration:none;padding:10px 22px;border-radius:8px;font-size:0.9rem;
                  font-weight:600;">Log In Now</a>
      </div>
    </div>
    """


def _send(to_email, subject, html_body):
    if not config.is_smtp_configured():
        log.info("SMTP not configured — skipping email send to %s", to_email)
        return False, "SMTP is not configured (set TSE_SMTP_* in .env) — credentials were shown on-screen instead."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        if config.SMTP_USE_TLS:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
                server.starttls(context=ssl.create_default_context())
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.sendmail(config.SMTP_FROM, [to_email], msg.as_string())
        else:
            with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.sendmail(config.SMTP_FROM, [to_email], msg.as_string())
        log.info("Sent email to %s: %s", to_email, subject)
        return True, None
    except Exception as e:
        log.exception("Failed to send email to %s", to_email)
        return False, f"Could not send email: {e}"


def send_registration_email(name, email, password):
    """Sent when an admin creates a new account. Returns (sent: bool, error: str|None)."""
    heading = f"Welcome to {config.APP_NAME}, {name}!"
    intro = ("Your account has been successfully created by the administrator. "
             "You can now access the platform using the credentials below.")
    html = _html_template(name, email, password, heading, intro)
    return _send(email, f"Welcome to {config.APP_NAME}", html)


def send_password_reset_email(name, email, password):
    """Sent when an admin resets a user's password. Returns (sent: bool, error: str|None)."""
    heading = f"Your password was reset, {name}"
    intro = ("An administrator has reset your password for the training platform. "
             "Use the new credentials below to log in.")
    html = _html_template(name, email, password, heading, intro)
    return _send(email, f"{config.APP_NAME} — password reset", html)
