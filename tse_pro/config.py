"""Centralized configuration for Talent Management Platform.

All environment-dependent values live here so nothing is hardcoded deep in
the app. Reads from a local .env file (if python-dotenv is installed and
the file exists) and falls back to sensible defaults for local development.
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars set another way still work

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------- Database ----------------
DB_PATH = os.environ.get("TSE_DB_PATH", os.path.join(BASE_DIR, "talent_sphere.db"))

# ---------------- Anthropic API ----------------
ANTHROPIC_MODEL = os.environ.get("TSE_MODEL", "claude-sonnet-4-6")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ---------------- Auth ----------------
PBKDF2_ITERATIONS = int(os.environ.get("TSE_PBKDF2_ITERATIONS", "200000"))
SEED_ADMIN_EMAIL = os.environ.get("TSE_SEED_ADMIN_EMAIL", "admin@talentsphere.com")
SEED_ADMIN_PASSWORD = os.environ.get("TSE_SEED_ADMIN_PASSWORD", "admin123")
MIN_PASSWORD_LENGTH = int(os.environ.get("TSE_MIN_PASSWORD_LENGTH", "8"))
MAX_LOGIN_ATTEMPTS = int(os.environ.get("TSE_MAX_LOGIN_ATTEMPTS", "5"))
LOGIN_LOCKOUT_MINUTES = int(os.environ.get("TSE_LOGIN_LOCKOUT_MINUTES", "10"))

# ---------------- RAG ----------------
CHUNK_WORDS = int(os.environ.get("TSE_CHUNK_WORDS", "150"))
CHUNK_OVERLAP = int(os.environ.get("TSE_CHUNK_OVERLAP", "30"))
DEFAULT_TOP_K = int(os.environ.get("TSE_DEFAULT_TOP_K", "4"))

# ---------------- App metadata ----------------
APP_NAME = "Talent Management Platform"
APP_FULL_NAME = "Talent Management Platform for Employee Performance and Career Growth"
APP_EDITION = "Pro"
APP_VERSION = "3.0.0"
APP_LOGIN_URL = os.environ.get("TSE_LOGIN_URL", "http://127.0.0.1:8501")

# ---------------- Email (SMTP) — used to send registration credentials ----------------
SMTP_HOST = os.environ.get("TSE_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("TSE_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("TSE_SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("TSE_SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("TSE_SMTP_FROM", SMTP_USER)
SMTP_USE_TLS = os.environ.get("TSE_SMTP_USE_TLS", "true").lower() != "false"


def is_smtp_configured():
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)

# ---------------- Courses & learner types ----------------
DEFAULT_COURSES = [
    "B.Tech — Computer Science", "B.Tech — Electronics & Communication",
    "B.Tech — Mechanical", "B.Tech — Civil", "B.Tech — Electrical",
    "BCA", "MCA", "M.Tech",
    "B.Sc — Computer Science", "B.Sc — Physics", "B.Sc — Chemistry", "B.Sc — Mathematics", "M.Sc",
    "B.Com", "M.Com", "BBA", "MBA",
    "BA — Economics", "BA — English", "MA",
    "LLB", "MBBS", "B.Pharm",
    "General / Other",
]

LEARNER_TYPES = [
    "Visual — diagrams, summaries, structured notes",
    "Auditory — voice explanations and spoken Q&A",
    "Reading/Writing — detailed text notes and written practice",
    "Kinesthetic — hands-on practice and frequent mock tests",
]

# ---------------- Logging ----------------
LOG_LEVEL = os.environ.get("TSE_LOG_LEVEL", "INFO")
LOG_PATH = os.environ.get("TSE_LOG_PATH", os.path.join(BASE_DIR, "app.log"))


def is_configured():
    """Returns True if the Anthropic API key is available from env (not just session)."""
    return bool(ANTHROPIC_API_KEY)
