"""Configuration loading and API key validation for plurity-mcp.

Resolution order (highest to lowest priority):
1. Environment variables
2. ~/.config/plurity/config.toml [mcp] section
3. Built-in defaults

After loading, the key is validated against the accounts API and the
enabled service set is intersected with the key's scopes.
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

_CONFIG_PATH = Path.home() / ".config" / "plurity" / "config.toml"

_DEFAULT_ACCOUNTS_URL = "https://account.plurity.ai"
_DEFAULT_AUDIT_URL = "https://audit.plurity.ai"
_DEFAULT_TOLL_URL = "https://toll.plurity.ai"
_DEFAULT_INTELLIGENCE_URL = "https://intelligence.plurity.ai"


# ---------------------------------------------------------------------------
# Scope helpers (mirrors the TypeScript hasScope in @plurity/auth)
# ---------------------------------------------------------------------------


def has_scope(key_scopes: list[str], required: str) -> bool:
    """Return True if *key_scopes* grants *required*.

    Supports wildcards:
      ["*"]          -> full access
      ["audit:*"]    -> all audit scopes
      ["audit:read"] -> exact match only
      ["audit"]      -> exact namespace match (convention: bare name = full access to service)
    """
    for scope in key_scopes:
        if scope == "*":
            return True
        if scope.endswith(":*"):
            ns = scope[:-2]
            if required == ns or required.startswith(ns + ":"):
                return True
        if scope == required:
            return True
    return False


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ServiceConfig:
    """Resolved configuration for one Plurity service."""

    enabled: bool
    """Whether this service's tools are registered."""

    base_url: str
    """Base URL for the service REST API."""


@dataclass(frozen=True, slots=True)
class PlurityMCPConfig:
    """Fully resolved configuration for plurity-mcp."""

    api_key: str
    accounts_url: str
    org_id: str
    scopes: list[str]
    audit: ServiceConfig
    toll: ServiceConfig
    intelligence: ServiceConfig


# ---------------------------------------------------------------------------
# TOML helpers
# ---------------------------------------------------------------------------


def _load_toml() -> dict:
    if not _CONFIG_PATH.exists():
        return {}
    with _CONFIG_PATH.open("rb") as fh:
        return tomllib.load(fh)


def _bool_env(name: str, default: bool) -> bool:
    val = os.environ.get(name, "").strip().lower()
    if val in ("0", "false", "no", "off"):
        return False
    if val in ("1", "true", "yes", "on"):
        return True
    return default


# ---------------------------------------------------------------------------
# Key validation
# ---------------------------------------------------------------------------


def _validate_key(api_key: str, accounts_url: str) -> tuple[str, str, list[str]]:
    """Validate *api_key* against the accounts API.

    Returns:
        (org_id, key_id, scopes) on success.

    Raises:
        RuntimeError with a descriptive message on failure.
    """
    url = f"{accounts_url.rstrip('/')}/api/v1/validate-key"
    try:
        response = httpx.post(
            url,
            json={"key": api_key},
            timeout=10.0,
            headers={"Content-Type": "application/json"},
        )
    except httpx.ConnectError:
        raise RuntimeError(
            f"Could not connect to the Plurity accounts API at {accounts_url}. "
            "Check your network connection or PLURITY_ACCOUNTS_URL."
        )
    except httpx.TimeoutException:
        raise RuntimeError(
            f"Timed out connecting to the Plurity accounts API at {accounts_url}."
        )

    if response.status_code == 401:
        raise RuntimeError(
            "Invalid API key. Check your PLURITY_API_KEY or run 'plurity-mcp-setup' "
            "to save a new key."
        )
    if response.status_code == 403:
        body = response.json()
        raise RuntimeError(f"API key rejected: {body.get('error', 'Forbidden')}")
    if not response.is_success:
        raise RuntimeError(
            f"Accounts API returned HTTP {response.status_code} when validating key."
        )

    body = response.json()
    return body["org_id"], body["key_id"], body.get("scopes", [])


# ---------------------------------------------------------------------------
# Main resolver
# ---------------------------------------------------------------------------


def get_config() -> PlurityMCPConfig:
    """Load, validate, and return the resolved :class:`PlurityMCPConfig`.

    Validates the API key against the accounts service and intersects the
    key's scopes with any user-level enable/disable overrides.

    Raises:
        RuntimeError if no API key is found or the key is invalid.
    """
    toml = _load_toml()
    mcp_section: dict = toml.get("mcp", {})

    # --- API key ---
    api_key = (
        os.environ.get("PLURITY_API_KEY", "").strip()
        or mcp_section.get("api_key", "").strip()
    )
    if not api_key:
        raise RuntimeError(
            "No Plurity API key found. "
            "Set the PLURITY_API_KEY environment variable or run 'plurity-mcp-setup'."
        )

    # --- Accounts URL ---
    accounts_url = (
        os.environ.get("PLURITY_ACCOUNTS_URL", "").strip()
        or mcp_section.get("accounts_url", "").strip()
        or _DEFAULT_ACCOUNTS_URL
    ).rstrip("/")

    # --- Validate key ---
    org_id, key_id, scopes = _validate_key(api_key, accounts_url)

    # --- Service base URLs ---
    audit_url = (
        os.environ.get("PLURITY_AUDIT_URL", "").strip()
        or mcp_section.get("audit_base_url", "").strip()
        or _DEFAULT_AUDIT_URL
    ).rstrip("/")

    toll_url = (
        os.environ.get("PLURITY_TOLL_URL", "").strip()
        or mcp_section.get("toll_base_url", "").strip()
        or _DEFAULT_TOLL_URL
    ).rstrip("/")

    intelligence_url = (
        os.environ.get("PLURITY_INTELLIGENCE_URL", "").strip()
        or mcp_section.get("intelligence_base_url", "").strip()
        or _DEFAULT_INTELLIGENCE_URL
    ).rstrip("/")

    # --- Service enablement ---
    # Scope check: does the key have access to each service?
    audit_scope_ok = has_scope(scopes, "audit")
    toll_scope_ok = has_scope(scopes, "toll")
    intelligence_scope_ok = has_scope(scopes, "intelligence")

    # User overrides (env vars or TOML); can only disable, not grant beyond scope
    audit_user_enabled = _bool_env("PLURITY_AUDIT_ENABLED", mcp_section.get("audit_enabled", True))
    toll_user_enabled = _bool_env("PLURITY_TOLL_ENABLED", mcp_section.get("toll_enabled", True))
    intelligence_user_enabled = _bool_env(
        "PLURITY_INTELLIGENCE_ENABLED", mcp_section.get("intelligence_enabled", True)
    )

    return PlurityMCPConfig(
        api_key=api_key,
        accounts_url=accounts_url,
        org_id=org_id,
        scopes=scopes,
        audit=ServiceConfig(
            enabled=audit_scope_ok and audit_user_enabled,
            base_url=audit_url,
        ),
        toll=ServiceConfig(
            enabled=toll_scope_ok and toll_user_enabled,
            base_url=toll_url,
        ),
        intelligence=ServiceConfig(
            enabled=intelligence_scope_ok and intelligence_user_enabled,
            base_url=intelligence_url,
        ),
    )


def save_config(
    api_key: str,
    accounts_url: str = _DEFAULT_ACCOUNTS_URL,
    audit_base_url: str = _DEFAULT_AUDIT_URL,
    toll_base_url: str = _DEFAULT_TOLL_URL,
    intelligence_base_url: str = _DEFAULT_INTELLIGENCE_URL,
) -> None:
    """Persist config to ``~/.config/plurity/config.toml`` under the ``[mcp]`` section."""
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing: dict = {}
    if _CONFIG_PATH.exists():
        with _CONFIG_PATH.open("rb") as fh:
            existing = tomllib.load(fh)

    existing.setdefault("mcp", {})
    existing["mcp"]["api_key"] = api_key
    existing["mcp"]["accounts_url"] = accounts_url
    existing["mcp"]["audit_base_url"] = audit_base_url
    existing["mcp"]["toll_base_url"] = toll_base_url
    existing["mcp"]["intelligence_base_url"] = intelligence_base_url

    lines: list[str] = []
    for section, values in existing.items():
        lines.append(f"[{section}]")
        for k, v in values.items():
            if isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
            else:
                lines.append(f'{k} = "{v}"')
        lines.append("")

    _CONFIG_PATH.write_text("\n".join(lines), encoding="utf-8")
