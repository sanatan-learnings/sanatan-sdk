"""Credential-loading utilities with consistent precedence across commands."""

import os
from pathlib import Path
from typing import Optional, Set

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def has_dotenv_support() -> bool:
    """Return True when python-dotenv is available."""
    return load_dotenv is not None


def _normalize_key(value: Optional[str], placeholder_values: Set[str]) -> Optional[str]:
    """Normalize candidate key values and filter placeholders."""
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized in placeholder_values:
        return None
    return normalized


def load_project_dotenv(project_dir: Optional[Path] = None, override: bool = False) -> bool:
    """
    Load .env without overriding already-exported environment variables.

    Returns True when python-dotenv is available and load was attempted.
    """
    if load_dotenv is None:
        return False

    base_dir = project_dir or Path.cwd()
    dotenv_path = base_dir / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path, override=override)
    else:
        load_dotenv(override=override)
    return True


def resolve_api_key(
    env_var: str,
    explicit_key: Optional[str] = None,
    project_dir: Optional[Path] = None,
    placeholder_values: Optional[Set[str]] = None,
) -> Optional[str]:
    """
    Resolve API key with precedence:
    1) explicit CLI key
    2) exported environment variable
    3) .env fallback
    """
    placeholders = set(placeholder_values or set())

    key = _normalize_key(explicit_key, placeholders)
    if key:
        return key

    env_value = os.environ.get(env_var)
    key = _normalize_key(env_value, placeholders)
    if key:
        return key

    should_override = env_value is not None
    load_project_dotenv(project_dir, override=should_override)
    return _normalize_key(os.environ.get(env_var), placeholders)
