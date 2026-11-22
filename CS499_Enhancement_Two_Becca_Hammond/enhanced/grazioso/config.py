# Becca Hammond
# CS499 Enhancement One - Software Design and Engineering
# 11/15/2026
# Version 1.0
#
# Purpose: Loads every setting the dashboard needs from environment variables
# (or a local .env file) instead of hard-coding them. The original notebook
# had the database username and password typed directly into the code, so
# anyone who could see the file could log in to the database.

import logging
import os
from dataclasses import dataclass
from typing import Mapping, Optional

from dotenv import load_dotenv

from grazioso.exceptions import ConfigError

###########################
# Required and default settings
###########################
# The username and password have no defaults on purpose. If they are missing
# the app stops at startup instead of guessing.
REQUIRED_SETTINGS = ("DB_USER", "DB_PASSWORD")

DEFAULT_DB_HOST = "localhost"
DEFAULT_DB_PORT = 27017
DEFAULT_DB_NAME = "aac"
DEFAULT_COLLECTION = "animals"
# The original connection string had no database after the host, so MongoDB
# checked the login against the admin database. Keeping that as the default.
DEFAULT_AUTH_SOURCE = "admin"
# mongosh uses a 2 second server selection timeout. PyMongo waits 30 seconds
# by default, which leaves the dashboard hanging when the database is down.
DEFAULT_TIMEOUT_MS = 5000
DEFAULT_APP_HOST = "127.0.0.1"
DEFAULT_APP_PORT = 8050
DEFAULT_LOG_LEVEL = "INFO"


@dataclass(frozen=True)
class AppConfig:
    """ All settings for one run of the dashboard """
    db_user: str
    db_password: str
    db_host: str = DEFAULT_DB_HOST
    db_port: int = DEFAULT_DB_PORT
    db_name: str = DEFAULT_DB_NAME
    collection_name: str = DEFAULT_COLLECTION
    auth_source: str = DEFAULT_AUTH_SOURCE
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    app_host: str = DEFAULT_APP_HOST
    app_port: int = DEFAULT_APP_PORT
    debug: bool = False
    log_level: str = DEFAULT_LOG_LEVEL

    def __repr__(self) -> str:
        # Never print the password, even in logs or error messages
        return (f"AppConfig(db_user={self.db_user!r}, db_password='***', "
                f"db_host={self.db_host!r}, db_port={self.db_port}, "
                f"db_name={self.db_name!r}, collection_name={self.collection_name!r})")


def _read_int(env: Mapping[str, str], name: str, default: int) -> int:
    # Ports and timeouts have to be whole numbers. A typo in the .env file
    # should stop the app with a clear message, not crash somewhere later.
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, got {raw!r}") from None
    if value <= 0:
        raise ConfigError(f"{name} must be greater than 0, got {value}")
    return value


def _read_bool(env: Mapping[str, str], name: str) -> bool:
    return env.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def load_config(env: Optional[Mapping[str, str]] = None) -> AppConfig:
    """
    Build an AppConfig from environment variables.
    Pass a dictionary for env to test without touching the real environment.
    Raises ConfigError if a required setting is missing or invalid.
    """
    if env is None:
        # Pull in a local .env file if there is one. Real environment
        # variables still win over anything in the file.
        load_dotenv()
        env = os.environ

    missing = [name for name in REQUIRED_SETTINGS if not env.get(name)]
    if missing:
        raise ConfigError("Missing required setting(s): " + ", ".join(missing)
                          + ". Copy .env.example to .env and fill them in.")

    return AppConfig(
        db_user=env["DB_USER"],
        db_password=env["DB_PASSWORD"],
        db_host=env.get("DB_HOST") or DEFAULT_DB_HOST,
        db_port=_read_int(env, "DB_PORT", DEFAULT_DB_PORT),
        db_name=env.get("DB_NAME") or DEFAULT_DB_NAME,
        collection_name=env.get("DB_COLLECTION") or DEFAULT_COLLECTION,
        auth_source=env.get("DB_AUTH_SOURCE") or DEFAULT_AUTH_SOURCE,
        timeout_ms=_read_int(env, "DB_TIMEOUT_MS", DEFAULT_TIMEOUT_MS),
        app_host=env.get("APP_HOST") or DEFAULT_APP_HOST,
        app_port=_read_int(env, "APP_PORT", DEFAULT_APP_PORT),
        debug=_read_bool(env, "APP_DEBUG"),
        log_level=(env.get("LOG_LEVEL") or DEFAULT_LOG_LEVEL).upper(),
    )


def setup_logging(level: str = DEFAULT_LOG_LEVEL) -> None:
    # One log format for the whole app. The original used print(), which
    # disappears once the app is running anywhere but a notebook.
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
