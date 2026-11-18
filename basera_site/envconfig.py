"""Small helpers for reading settings from environment variables.

Kept apart from settings.py so they can be tested on their own.
"""

import os
from urllib.parse import parse_qs, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

TRUE_WORDS = ("1", "true", "yes", "on")


def flag(name, default):
    """A yes/no setting: 1, true, yes or on (any case) means True; anything else False."""
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in TRUE_WORDS


def csv(name):
    """A comma-separated setting as a clean list (blank items dropped)."""
    return [item.strip() for item in (os.environ.get(name) or "").split(",") if item.strip()]


def database_from_url(url):
    """Turn postgres://user:password@host:5432/name into a Django DATABASES entry.

    Hosting services such as Render hand out the database as one DATABASE_URL.
    A ?sslmode=require style option is passed through to the driver.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("postgres", "postgresql"):
        raise ImproperlyConfigured("DATABASE_URL must start with postgres:// or postgresql://")
    name = parsed.path.lstrip("/")
    if not name or not parsed.hostname:
        raise ImproperlyConfigured("DATABASE_URL needs a host and a database name.")
    config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(name),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname,
        "PORT": str(parsed.port or 5432),
    }
    options = {key: values[-1] for key, values in parse_qs(parsed.query).items() if key == "sslmode"}
    if options:
        config["OPTIONS"] = options
    return config
