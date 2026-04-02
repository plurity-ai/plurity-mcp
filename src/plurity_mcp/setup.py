"""Interactive CLI for first-time setup of plurity-mcp.

Run with:
    plurity-mcp-setup
"""

from __future__ import annotations

import sys

from .config import (
    _CONFIG_PATH,
    _DEFAULT_ACCOUNTS_URL,
    _DEFAULT_AUDIT_URL,
    _DEFAULT_INTELLIGENCE_URL,
    _DEFAULT_TOLL_URL,
    _validate_key,
    save_config,
)


_CLAUDE_DESKTOP_EXAMPLE = """\
{
  "mcpServers": {
    "plurity": {
      "command": "uvx",
      "args": ["plurity-mcp"],
      "env": {
        "PLURITY_API_KEY": "plt_your_key_here"
      }
    }
  }
}"""

_CLAUDE_DESKTOP_DISABLE_EXAMPLE = """\
{
  "mcpServers": {
    "plurity": {
      "command": "uvx",
      "args": ["plurity-mcp"],
      "env": {
        "PLURITY_API_KEY": "plt_your_key_here",
        "PLURITY_TOLL_ENABLED": "false"
      }
    }
  }
}"""


def main() -> None:
    """Interactive setup wizard."""
    print("\nPlurity MCP — setup\n" + "-" * 35)
    print(
        "\nThis server provides a single MCP interface to all Plurity services "
        "(Audit, Toll, Intelligence) using one API key.\n"
    )
    print(
        "Step 1  Go to https://account.plurity.ai/settings/api-keys "
        "and create an API key.\n"
        "        Make sure to grant it access to the services you want to use.\n"
    )

    try:
        raw = input("Step 2  Paste your API key (plt_...): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.")
        sys.exit(1)

    if not raw:
        print("No key entered. Setup cancelled.")
        sys.exit(1)

    if not raw.startswith("plt_"):
        print("Warning: key does not start with 'plt_'. Saving anyway.")

    # Validate before saving
    print("\nValidating key...", end="", flush=True)
    try:
        org_id, key_id, scopes = _validate_key(raw, _DEFAULT_ACCOUNTS_URL)
        print(f" OK  (org: {org_id}, scopes: {', '.join(scopes) or 'none'})")
    except RuntimeError as exc:
        print(f"\nError: {exc}")
        try:
            proceed = input("Save anyway? [y/N] ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            proceed = "n"
        if proceed != "y":
            print("Setup cancelled.")
            sys.exit(1)

    save_config(
        api_key=raw,
        accounts_url=_DEFAULT_ACCOUNTS_URL,
        audit_base_url=_DEFAULT_AUDIT_URL,
        toll_base_url=_DEFAULT_TOLL_URL,
        intelligence_base_url=_DEFAULT_INTELLIGENCE_URL,
    )

    print(f"\nSaved to {_CONFIG_PATH}")
    print("\nStep 3  Add the server to your MCP client.\n")
    print(
        "Claude Desktop — add to "
        "~/Library/Application Support/Claude/claude_desktop_config.json:\n"
    )
    for line in _CLAUDE_DESKTOP_EXAMPLE.splitlines():
        print(f"  {line}")

    print("\nTo disable a specific service, set the corresponding env var:")
    for line in _CLAUDE_DESKTOP_DISABLE_EXAMPLE.splitlines():
        print(f"  {line}")

    print(
        "\nAvailable disable flags:\n"
        "  PLURITY_AUDIT_ENABLED=false\n"
        "  PLURITY_TOLL_ENABLED=false\n"
        "  PLURITY_INTELLIGENCE_ENABLED=false\n"
    )
    print("Done!")
