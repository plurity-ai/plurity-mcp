"""MCP tools for the Plurity Intelligence service (question & topic monitoring)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

from ..client import IntelligenceClient, PlurityAPIError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..config import PlurityMCPConfig


def register_intelligence_tools(mcp: "FastMCP", config: "PlurityMCPConfig") -> None:
    """Register all Intelligence tools on *mcp*."""

    def _client() -> IntelligenceClient:
        return IntelligenceClient(
            api_key=config.api_key, base_url=config.intelligence.base_url
        )

    def _ok(data: object) -> str:
        return json.dumps(data, ensure_ascii=False)

    def _err(message: str) -> str:
        return json.dumps({"error": message})

    def _wrap(fn):
        try:
            with _client() as c:
                return _ok(fn(c))
        except PlurityAPIError as exc:
            return _err(str(exc))
        except Exception as exc:
            return _err(f"Unexpected error: {exc}")

    # ------------------------------------------------------------------
    # Sources (global registry + subscriptions)
    # ------------------------------------------------------------------

    @mcp.tool()
    def list_intelligence_sources(
        source_type: Optional[str] = None,
        query: Optional[str] = None,
    ) -> str:
        """List all available content sources in the Plurity Intelligence catalogue.

        This is the global registry of sources Plurity monitors — LinkedIn
        profiles, YouTube channels, publishers, newsletters, and academic
        publications. Use ``list_subscribed_intelligence_sources`` to see
        which ones your organisation follows.

        Args:
            source_type: Filter by type — one of ``"linkedin"``, ``"youtube"``,
                         ``"publisher"``, ``"newsletter"``, ``"academic"``.
            query: Free-text search against source names and descriptions.

        Returns:
            JSON with a ``sources`` array. Each item has ``id``, ``name``,
            ``handle``, ``url``, ``type``, ``description``, ``tags``,
            ``avatar_url``, ``follower_count``, ``post_frequency``.
        """
        return _wrap(lambda c: c.list_sources(type=source_type, q=query))

    @mcp.tool()
    def list_subscribed_intelligence_sources() -> str:
        """List the content sources your organisation is subscribed to.

        Returns the subset of the global catalogue that your org follows,
        along with subscription metadata (start date, subscribed at).

        Returns:
            JSON with a ``subscriptions`` array. Each item has ``source_id``,
            ``source`` (full source object), ``start_date``, ``subscribed_at``.
        """
        return _wrap(lambda c: c.list_subscriptions())

    @mcp.tool()
    def subscribe_intelligence_source(
        source_id: str,
        start_date: Optional[str] = None,
    ) -> str:
        """Subscribe your organisation to a content source.

        Once subscribed, new content from this source will be scraped and
        Q&A pairs will be extracted for your organisation's feed.

        Args:
            source_id: The source UUID (from ``list_intelligence_sources``).
            start_date: ISO 8601 date (``"YYYY-MM-DD"``) from which to fetch
                        content. Defaults to 7 days ago if omitted.

        Returns:
            JSON ``{"ok": true}`` on success.
        """
        return _wrap(
            lambda c: c.subscribe_source(source_id=source_id, start_date=start_date)
        )

    @mcp.tool()
    def unsubscribe_intelligence_source(source_id: str) -> str:
        """Unsubscribe your organisation from a content source.

        Stops new content from this source being processed for your org.
        Existing Q&A pairs and content pieces are not deleted.

        Args:
            source_id: The source UUID.

        Returns:
            JSON ``{"ok": true}`` on success.
        """
        return _wrap(lambda c: c.unsubscribe_source(source_id=source_id))

    @mcp.tool()
    def request_intelligence_source(url: str) -> str:
        """Request a new source to be added to the Intelligence catalogue.

        If the URL matches an existing source it will be subscribed to
        immediately. Otherwise a new source record is created (with type
        auto-detected from the domain) and your org is subscribed.

        Args:
            url: Full URL of the source — e.g. a LinkedIn profile
                 (``"https://linkedin.com/in/username"``), YouTube channel
                 (``"https://youtube.com/@handle"``), or website homepage.

        Returns:
            JSON with ``ok``, ``source_id``, and whether it was
            ``newly_created``.
        """
        return _wrap(lambda c: c.request_source(url=url))

    # ------------------------------------------------------------------
    # Source content (raw scraped documents)
    # ------------------------------------------------------------------

    @mcp.tool()
    def list_intelligence_source_content(
        source_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> str:
        """List raw content documents scraped from sources.

        These are the individual articles, videos, posts, or newsletter
        issues that have been scraped. Q&A pairs are extracted from these.

        Args:
            source_id: Filter to content from a specific source UUID.
            date_from: ISO 8601 date (``"YYYY-MM-DD"``) — only content
                       published on or after this date.
            date_to: ISO 8601 date — only content published on or before
                     this date.
            content_type: Filter by type — one of ``"article"``, ``"video"``,
                          ``"post"``, ``"newsletter"``, ``"paper"``.

        Returns:
            JSON with a ``content`` array. Each item has ``id``, ``source_id``,
            ``url``, ``title``, ``content_type``, ``content_date``,
            ``scraped_at``.
        """
        return _wrap(
            lambda c: c.list_source_content(
                source_id=source_id,
                date_from=date_from,
                date_to=date_to,
                content_type=content_type,
            )
        )

    # ------------------------------------------------------------------
    # Q&A feed
    # ------------------------------------------------------------------

    @mcp.tool()
    def list_intelligence_qa_pairs(
        source_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None,
    ) -> str:
        """List Q&A pairs extracted from your subscribed sources.

        This is your organisation's feed of AI-extracted question-and-answer
        pairs. Review them here before promoting to your knowledge base.

        Args:
            source_id: Filter to pairs from a specific source UUID.
            date_from: ISO 8601 date — only pairs created on or after this date.
            date_to: ISO 8601 date — only pairs created on or before this date.
            status: Filter by status — one of ``"pending"``, ``"approved"``,
                    ``"skipped"``. Defaults to showing all statuses.

        Returns:
            JSON with a ``qa_pairs`` array. Each item has ``id``, ``org_id``,
            ``source_id``, ``question``, ``answer``, ``confidence``,
            ``topics``, ``status``, ``created_at``, and ``updated_at``.
        """
        return _wrap(
            lambda c: c.list_qa_pairs(
                source_id=source_id,
                date_from=date_from,
                date_to=date_to,
                status=status,
            )
        )

    @mcp.tool()
    def approve_intelligence_qa_pair(qa_pair_id: str) -> str:
        """Approve a Q&A pair and add it to your organisation's knowledge base.

        Marks the pair as ``approved`` and copies it into your content base
        (``content_pieces`` table), making it available for export to
        llms.txt and other downstream uses.

        Args:
            qa_pair_id: The Q&A pair UUID.

        Returns:
            JSON ``{"ok": true}`` on success.
        """
        return _wrap(lambda c: c.approve_qa_pair(qa_pair_id=qa_pair_id))

    @mcp.tool()
    def skip_intelligence_qa_pair(qa_pair_id: str) -> str:
        """Skip a Q&A pair so it no longer appears in the pending feed.

        Marks the pair as ``skipped``. This does not delete it — you can
        still retrieve it with ``list_intelligence_qa_pairs`` by filtering
        on ``status="skipped"``.

        Args:
            qa_pair_id: The Q&A pair UUID.

        Returns:
            JSON ``{"ok": true}`` on success.
        """
        return _wrap(lambda c: c.skip_qa_pair(qa_pair_id=qa_pair_id))
