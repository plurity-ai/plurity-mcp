"""Unified Plurity MCP server.

Validates the API key against plurity-accounts on startup, then registers
only the tools for services the key has access to (and that are not
explicitly disabled in config).
"""

from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Plurity")


def main() -> None:
    """Validate config and start the MCP server."""
    from .config import get_config

    try:
        config = get_config()
    except RuntimeError as exc:
        # Print a clear message to stderr so the MCP client (e.g. Claude
        # Desktop) can surface it to the user.
        print(f"[plurity-mcp] Configuration error: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)

    enabled: list[str] = []
    disabled_by_scope: list[str] = []

    if config.audit.enabled:
        from .tools.audit import register_audit_tools
        register_audit_tools(mcp, config)
        enabled.append("audit")
    else:
        disabled_by_scope.append("audit")

    if config.toll.enabled:
        from .tools.toll import register_toll_tools
        register_toll_tools(mcp, config)
        enabled.append("toll")
    else:
        disabled_by_scope.append("toll")

    if config.intelligence.enabled:
        from .tools.intelligence import register_intelligence_tools
        register_intelligence_tools(mcp, config)
        enabled.append("intelligence")
    else:
        disabled_by_scope.append("intelligence")

    if not enabled:
        print(
            "[plurity-mcp] No services are enabled. "
            "Your key's scopes may not grant access to any service, "
            "or all services were manually disabled.\n"
            f"Key scopes: {config.scopes}",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)

    summary = f"[plurity-mcp] Starting — services: {', '.join(enabled)}"
    if disabled_by_scope:
        summary += f" | disabled: {', '.join(disabled_by_scope)}"
    print(summary, file=sys.stderr, flush=True)

    mcp.run()
