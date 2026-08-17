"""Shared logger for Talent Management Platform. Import get_logger(__name__) anywhere."""
import logging
import config

_configured = False


def _configure_root():
    global _configured
    if _configured:
        return
    handlers = [logging.StreamHandler()]
    try:
        handlers.append(logging.FileHandler(config.LOG_PATH))
    except OSError:
        pass  # e.g. read-only filesystem in some deployments — console logging still works
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )
    _configured = True


def get_logger(name):
    _configure_root()
    return logging.getLogger(name)
