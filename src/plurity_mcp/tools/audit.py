"""MCP tools for the Plurity GEO Audit service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..client import AuditClient, PlurityAPIError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..config import PlurityMCPConfig


def register_audit_tools(mcp: "FastMCP", config: "PlurityMCPConfig") -> None:
    """Register all audit tools on *mcp*."""

    def _client() -> AuditClient:
        return AuditClient(api_key=config.api_key, base_url=config.audit.base_url)

    @mcp.tool()
    def submit_audit_scan(url: str, webhook_url: str = "") -> str:
        """Submit a URL for a GEO (Generative Engine Optimisation) audit scan.

        Queues the URL for a full Playwright crawl followed by AI analysis.
        The scan runs asynchronously. Use ``get_audit_scan`` to poll for
        results or use ``run_audit`` to block until the scan completes.

        Args:
            url: The website URL to audit (e.g. "https://example.com").
            webhook_url: Optional HTTPS URL to notify when the scan finishes.

        Returns:
            JSON with ``id``, ``scan_result_id``, ``status``, and
            ``cached`` (true if results were already available).
        """
        import json
        try:
            with _client() as c:
                return json.dumps(c.submit_scan(url=url, webhook_url=webhook_url))
        except PlurityAPIError as exc:
            return json.dumps({"error": str(exc)})
        except Exception as exc:
            return json.dumps({"error": f"Unexpected error: {exc}"})

    @mcp.tool()
    def get_audit_scan(scan_id: str) -> str:
        """Get the current status and results of an audit scan by its ID.

        Args:
            scan_id: The scan ID returned by ``submit_audit_scan`` (the ``id`` field).

        Returns:
            JSON with ``id``, ``scan_result_id``, ``url``, ``status``,
            ``overall_score`` (0–100 or null), ``analysis`` (object or null),
            ``error`` (string or null), ``submitted_at``, and ``updated_at``.
            Status is one of: ``pending``, ``crawling``, ``analyzing``,
            ``complete``, ``failed``.
        """
        import json
        try:
            with _client() as c:
                return json.dumps(c.get_scan(scan_id=scan_id))
        except PlurityAPIError as exc:
            return json.dumps({"error": str(exc)})
        except Exception as exc:
            return json.dumps({"error": f"Unexpected error: {exc}"})

    @mcp.tool()
    def get_audit_scan_by_url(url: str) -> str:
        """Look up the latest audit scan result for a given URL.

        Useful for checking whether a site has already been scanned without
        knowing its scan ID.

        Args:
            url: The website URL to look up (e.g. "https://example.com").

        Returns:
            JSON with the same shape as ``get_audit_scan``, or an error
            object if no scan exists for that URL.
        """
        import json
        try:
            with _client() as c:
                return json.dumps(c.get_scan_by_url(url=url))
        except PlurityAPIError as exc:
            return json.dumps({"error": str(exc)})
        except Exception as exc:
            return json.dumps({"error": f"Unexpected error: {exc}"})

    @mcp.tool()
    def run_audit(url: str, timeout_seconds: int = 300) -> str:
        """Submit a URL for a full GEO audit and wait until it completes.

        Submits the URL and blocks, polling every 5 seconds until the scan
        reaches a terminal state (``complete`` or ``failed``) or the timeout
        is exceeded. Cached results are returned immediately.

        Args:
            url: The website URL to audit (e.g. "https://example.com").
            timeout_seconds: Maximum wait time in seconds (default 300, max 900).

        Returns:
            JSON with the full scan result including ``overall_score`` and
            ``analysis`` when complete. If the timeout is exceeded the last
            known status is returned — check the ``status`` field.
        """
        import json
        if timeout_seconds < 1:
            return json.dumps({"error": "timeout_seconds must be at least 1."})
        if timeout_seconds > 900:
            return json.dumps({"error": "timeout_seconds must not exceed 900 (15 minutes)."})
        try:
            with _client() as c:
                submitted = c.submit_scan(url=url)
                if submitted.get("status") in {"complete", "failed"}:
                    return json.dumps(submitted)
                scan_id = submitted.get("id", "")
                if not scan_id:
                    return json.dumps({"error": "API did not return a scan ID."})
                result = c.wait_for_scan(scan_id=scan_id, timeout_seconds=timeout_seconds)
                return json.dumps(result)
        except PlurityAPIError as exc:
            return json.dumps({"error": str(exc)})
        except Exception as exc:
            return json.dumps({"error": f"Unexpected error: {exc}"})
