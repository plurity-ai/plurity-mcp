"""MCP tools for the Plurity Toll service (agent traffic + llms.txt management)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

from ..client import TollClient, PlurityAPIError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..config import PlurityMCPConfig


def register_toll_tools(mcp: "FastMCP", config: "PlurityMCPConfig") -> None:
    """Register all Toll tools on *mcp*."""

    def _client() -> TollClient:
        return TollClient(api_key=config.api_key, base_url=config.toll.base_url)

    def _ok(data: object) -> str:
        return json.dumps(data, ensure_ascii=False)

    def _err(message: str) -> str:
        return json.dumps({"error": message})

    def _wrap(fn):
        """Call *fn(client)* and convert errors to JSON strings."""
        try:
            with _client() as c:
                return _ok(fn(c))
        except PlurityAPIError as exc:
            return _err(str(exc))
        except Exception as exc:
            return _err(f"Unexpected error: {exc}")

    # ------------------------------------------------------------------
    # Sites (pages)
    # ------------------------------------------------------------------

    @mcp.tool()
    def list_toll_sites() -> str:
        """List all Toll sites (pages) owned by your organisation.

        Each site represents a domain where the Toll tracking snippet is
        installed and where llms.txt is served.

        Returns:
            JSON with a ``sites`` array. Each item has ``id``, ``name``,
            ``domain``, ``llms_txt_mode``, ``cache_ttl_secs``, ``created_at``,
            ``updated_at``.
        """
        return _wrap(lambda c: c.list_sites())

    @mcp.tool()
    def create_toll_site(name: str, domain: str) -> str:
        """Create a new Toll site.

        Args:
            name: Human-readable site name (e.g. "Acme Corp").
            domain: The domain to track, without protocol or trailing slash
                    (e.g. "acme.com" or "docs.acme.com").

        Returns:
            JSON with the created site including its ``id`` and ``site_key``
            (needed for the tracking snippet).
        """
        return _wrap(lambda c: c.create_site(name=name, domain=domain))

    @mcp.tool()
    def get_toll_site(site_id: str) -> str:
        """Get full details for a Toll site, including the installation key.

        Args:
            site_id: The site UUID.

        Returns:
            JSON with site details including ``site_key``, ``llms_txt_mode``,
            ``cache_ttl_secs``, ``llms_preamble``, and timestamps.
        """
        return _wrap(lambda c: c.get_site(site_id=site_id))

    @mcp.tool()
    def update_toll_site(
        site_id: str,
        name: Optional[str] = None,
        domain: Optional[str] = None,
        cache_ttl_secs: Optional[int] = None,
        llms_txt_mode: Optional[str] = None,
        llms_preamble: Optional[str] = None,
    ) -> str:
        """Update settings for a Toll site.

        All parameters are optional; only the fields you pass will be changed.

        Args:
            site_id: The site UUID.
            name: New human-readable name.
            domain: New domain (without protocol or trailing slash).
            cache_ttl_secs: How long the SDK caches the llms.txt response in
                            seconds (e.g. 3600 for 1 hour).
            llms_txt_mode: How llms.txt questions are managed.
                           ``"manual"`` — you control Q&A pairs entirely.
                           ``"cms"`` — questions are auto-populated from CMS.
            llms_preamble: Custom preamble text shown at the top of
                           llms.txt/llms-full.txt, above the Q&A list (e.g.
                           a short site description or agent instructions).
                           Pass an empty string to clear it and fall back to
                           the default preamble (which tells agents how to
                           submit unanswered questions).

        Returns:
            JSON with the updated site.
        """
        return _wrap(
            lambda c: c.update_site(
                site_id=site_id,
                name=name,
                domain=domain,
                cache_ttl_secs=cache_ttl_secs,
                llms_txt_mode=llms_txt_mode,
                llms_preamble=llms_preamble,
            )
        )

    @mcp.tool()
    def get_toll_installation_instructions(
        site_id: str,
        framework: str = "all",
    ) -> str:
        """Get installation instructions for adding Toll tracking to a project.

        Fetches the site details and returns markdown-formatted, step-by-step
        instructions for integrating the tracking snippet for the specified
        framework.

        Args:
            site_id: The site UUID.
            framework: The target framework. One of ``"squarespace"``,
                       ``"nextjs"``, ``"express"``, ``"html"``, or ``"all"``
                       (default). When ``"all"`` is given, instructions for
                       every framework are returned; otherwise only the
                       requested framework's instructions are included.

        Returns:
            JSON with ``site_id``, ``site_key``, ``domain``, ``framework``,
            and ``instructions`` — an object whose keys are framework names
            and whose values are markdown-formatted installation guides.
        """
        try:
            with _client() as c:
                site = c.get_site(site_id=site_id)
        except PlurityAPIError as exc:
            return _err(str(exc))
        except Exception as exc:
            return _err(f"Unexpected error: {exc}")

        site_key = site.get("site", {}).get("site_key", site.get("site_key", ""))
        domain = site.get("site", {}).get("domain", site.get("domain", ""))
        toll_base = config.toll.base_url

        def _sub(template: str) -> str:
            """Substitute site-specific values into a markdown template."""
            return (
                template
                .replace("{site_id}", site_id)
                .replace("{site_key}", site_key)
                .replace("{toll_base}", toll_base)
            )

        squarespace_md = _sub(
            "## Squarespace Setup\n"
            "\n"
            "**Step 1 — Add the script tag**\n"
            "\n"
            "In Squarespace → Settings → Advanced → Code Injection (header), paste:\n"
            "\n"
            "```html\n"
            "<script\n"
            "  src=\"https://cdn.plurity.ai/toll.js\"\n"
            "  data-site-id=\"{site_id}\"\n"
            "  data-site-key=\"{site_key}\"\n"
            "  async\n"
            "></script>\n"
            "```\n"
            "\n"
            "**Step 2 — llms.txt redirect**\n"
            "\n"
            "In Squarespace → Settings → Advanced → URL Redirects, add a 301 redirect:\n"
            "- From: `/llms.txt`\n"
            "- To: `{toll_base}/api/public/{site_id}/llms.txt?key={site_key}`\n"
            "\n"
            "**Step 3 — llms-full.txt redirect (optional)**\n"
            "\n"
            "Add another 301 redirect:\n"
            "- From: `/llms-full.txt`\n"
            "- To: `{toll_base}/api/public/{site_id}/llms-full.txt?key={site_key}`\n"
        )

        nextjs_md = _sub(
            "## Next.js Setup\n"
            "\n"
            "**Step 1 — Install**\n"
            "\n"
            "```bash\n"
            "npm install @plurity/toll-nextjs\n"
            "```\n"
            "\n"
            "**Step 2 — Add to .env.local**\n"
            "\n"
            "```\n"
            "TOLL_SITE_ID={site_id}\n"
            "TOLL_SITE_KEY={site_key}\n"
            "```\n"
            "\n"
            "**Step 3 — Add to middleware.ts**\n"
            "\n"
            "```typescript\n"
            "import { createTollMiddleware } from '@plurity/toll-nextjs'\n"
            "import type { NextRequest } from 'next/server'\n"
            "import { NextResponse } from 'next/server'\n"
            "\n"
            "const toll = createTollMiddleware({\n"
            "  siteId: process.env.TOLL_SITE_ID!,\n"
            "  siteKey: process.env.TOLL_SITE_KEY!,\n"
            "})\n"
            "\n"
            "export async function middleware(request: NextRequest) {\n"
            "  const tollResponse = await toll(request)\n"
            "  if (tollResponse) return tollResponse\n"
            "  return NextResponse.next()\n"
            "}\n"
            "```\n"
        )

        express_md = _sub(
            "## Express Setup\n"
            "\n"
            "**Step 1 — Install**\n"
            "\n"
            "```bash\n"
            "npm install @plurity/toll @plurity/toll-express\n"
            "```\n"
            "\n"
            "**Step 2 — Add environment variables**\n"
            "\n"
            "```\n"
            "TOLL_SITE_ID={site_id}\n"
            "TOLL_SITE_KEY={site_key}\n"
            "```\n"
            "\n"
            "**Step 3 — Add middleware**\n"
            "\n"
            "```typescript\n"
            "import { createTollMiddleware, createLlmsTxtHandler } from '@plurity/toll-express'\n"
            "import { PlurityBackend } from '@plurity/toll'\n"
            "\n"
            "const backend = new PlurityBackend({ siteKey: process.env.TOLL_SITE_KEY! })\n"
            "\n"
            "app.use(createTollMiddleware({ siteId: process.env.TOLL_SITE_ID!, backend }))\n"
            "app.get('/llms.txt', createLlmsTxtHandler({ siteId: process.env.TOLL_SITE_ID!, backend }))\n"
            "```\n"
        )

        html_md = _sub(
            "## HTML / Any Site Setup\n"
            "\n"
            "**Step 1 — Add the script tag**\n"
            "\n"
            "Paste before `</body>` on every page:\n"
            "\n"
            "```html\n"
            "<script\n"
            "  src=\"https://cdn.plurity.ai/toll.js\"\n"
            "  data-site-id=\"{site_id}\"\n"
            "  data-site-key=\"{site_key}\"\n"
            "  async\n"
            "></script>\n"
            "```\n"
            "\n"
            "**Step 2 — Serve llms.txt**\n"
            "\n"
            "Redirect `/llms.txt` on your server to:\n"
            "`{toll_base}/api/public/{site_id}/llms.txt?key={site_key}`\n"
        )

        all_instructions = {
            "squarespace": squarespace_md,
            "nextjs": nextjs_md,
            "express": express_md,
            "html": html_md,
        }

        valid_frameworks = set(all_instructions.keys()) | {"all"}
        if framework not in valid_frameworks:
            return _err(
                f"Unknown framework {framework!r}. "
                f"Valid values: {sorted(valid_frameworks)}"
            )

        if framework == "all":
            instructions = all_instructions
        else:
            instructions = {framework: all_instructions[framework]}

        return _ok({
            "site_id": site_id,
            "site_key": site_key,
            "domain": domain,
            "framework": framework,
            "instructions": instructions,
        })

    # ------------------------------------------------------------------
    # Q&A pairs (llms.txt content)
    # ------------------------------------------------------------------

    @mcp.tool()
    def list_toll_qa_pairs(site_id: str) -> str:
        """List all Q&A pairs for a Toll site's llms.txt.

        Q&A pairs define the questions-and-answers served in llms.txt,
        helping AI agents understand your site's content and context.

        Args:
            site_id: The site UUID.

        Returns:
            JSON with a ``qa_pairs`` array. Each item has ``id``,
            ``question``, ``answer_url``, ``answer_summary``,
            ``redirect_url``, ``slug``, ``answer_content``, ``sort_order``,
            ``is_published``, ``created_at``, ``updated_at``.
        """
        return _wrap(lambda c: c.list_qa_pairs(site_id=site_id))

    @mcp.tool()
    def create_toll_qa_pair(
        site_id: str,
        question: str,
        answer_url: str,
        answer_summary: Optional[str] = None,
        redirect_url: Optional[str] = None,
        slug: Optional[str] = None,
        answer_content: Optional[str] = None,
    ) -> str:
        """Add a new Q&A pair to a Toll site's llms.txt.

        This is the core shadow-page primitive: it defines both what an AI
        agent reading llms.txt sees, and where a human clicking the same
        tracked link ends up.

        Args:
            site_id: The site UUID.
            question: The question an AI agent might ask
                      (e.g. "What is your return policy?").
            answer_url: The agent-facing content entry point for this
                        answer (e.g. "https://acme.com/returns"). This is
                        what an agent following the link is aiming for.
            answer_summary: Optional short plain-text summary of the answer
                            (max ~200 chars), shown inline in llms.txt so
                            agents get the gist without visiting the page.
            redirect_url: Optional URL a *human* lands on when they click
                          the tracked link in llms.txt, if different from
                          answer_url (e.g. a nicer landing page vs. the raw
                          content path). Falls back to the site's domain
                          root when omitted.
            slug: Optional CMS route slug. When set, agents following the
                  tracked link get ``answer_content`` served inline as
                  markdown instead of being redirected — this is the
                  "shadow page" behavior. Must be unique per site.
            answer_content: Optional full markdown answer, served inline to
                            agents (via the slug) and included in
                            llms-full.txt. Use this for the complete,
                            detailed answer beyond the short summary.

        Returns:
            JSON with the created Q&A pair.
        """
        return _wrap(
            lambda c: c.create_qa_pair(
                site_id=site_id,
                question=question,
                answer_url=answer_url,
                answer_summary=answer_summary,
                redirect_url=redirect_url,
                slug=slug,
                answer_content=answer_content,
            )
        )

    @mcp.tool()
    def update_toll_qa_pair(
        site_id: str,
        pair_id: str,
        question: Optional[str] = None,
        answer_url: Optional[str] = None,
        answer_summary: Optional[str] = None,
        redirect_url: Optional[str] = None,
        slug: Optional[str] = None,
        answer_content: Optional[str] = None,
        is_published: Optional[bool] = None,
    ) -> str:
        """Update an existing Q&A pair.

        All fields are optional; only the fields you pass will change. Use
        this to iterate on shadow-page content (question phrasing, summary,
        full answer, slug, redirect target) until an agent retrieves the
        right answer for a given question.

        Args:
            site_id: The site UUID.
            pair_id: The Q&A pair UUID.
            question: New question text.
            answer_url: New agent-facing answer page URL.
            answer_summary: New plain-text summary.
            redirect_url: New human landing page URL (distinct from
                          answer_url — see create_toll_qa_pair).
            slug: New CMS route slug (enables inline shadow-page content
                  for agents via answer_content).
            answer_content: New full markdown answer served inline to
                            agents and in llms-full.txt.
            is_published: Whether this pair appears in the public llms.txt.
                          Set to ``false`` to hide it without deleting it.

        Returns:
            JSON with the updated Q&A pair.
        """
        return _wrap(
            lambda c: c.update_qa_pair(
                site_id=site_id,
                pair_id=pair_id,
                question=question,
                answer_url=answer_url,
                answer_summary=answer_summary,
                redirect_url=redirect_url,
                slug=slug,
                answer_content=answer_content,
                is_published=is_published,
            )
        )

    @mcp.tool()
    def get_toll_llms_txt(site_id: str, full: bool = False) -> str:
        """Fetch the live llms.txt (or llms-full.txt) as served to AI agents.

        This is exactly what an agent reading your site's llms.txt sees —
        useful for checking whether a question is answered clearly before
        testing real-world discovery, and for verifying edits made via
        create_toll_qa_pair / update_toll_qa_pair took effect.

        Args:
            site_id: The site UUID.
            full: If true, fetch llms-full.txt (includes full answer_content
                  for each published Q&A pair). If false (default), fetch
                  the brief llms.txt (question + short summary only).

        Returns:
            JSON with ``site_id``, ``full``, and ``llms_txt`` (the raw
            served text).
        """
        def _fetch(c: TollClient) -> dict:
            site = c.get_site(site_id=site_id)
            site_key = site.get("site", {}).get("site_key", site.get("site_key", ""))
            text = c.get_llms_txt(site_id=site_id, site_key=site_key, full=full)
            return {"site_id": site_id, "full": full, "llms_txt": text}

        return _wrap(_fetch)

    @mcp.tool()
    def delete_toll_qa_pair(site_id: str, pair_id: str) -> str:
        """Delete a Q&A pair from a Toll site.

        This permanently removes the pair. Consider using
        ``update_toll_qa_pair`` with ``is_published=false`` to hide it
        without losing the content.

        Args:
            site_id: The site UUID.
            pair_id: The Q&A pair UUID to delete.

        Returns:
            JSON ``{"ok": true}`` on success.
        """
        return _wrap(lambda c: c.delete_qa_pair(site_id=site_id, pair_id=pair_id))

    # ------------------------------------------------------------------
    # Traffic
    # ------------------------------------------------------------------

    @mcp.tool()
    def get_toll_traffic(
        site_id: str,
        period: str = "week",
        agents: Optional[str] = None,
    ) -> str:
        """Get agent traffic data for a Toll site.

        Returns time-bucketed visit counts broken down by AI agent / bot type.

        Args:
            site_id: The site UUID.
            period: Time range — one of ``"today"``, ``"week"`` (last 7 days),
                    ``"month"`` (last 30 days), ``"year"`` (last 12 months).
                    Defaults to ``"week"``.
            agents: Optional comma-separated list of agent names to filter to
                    (e.g. ``"GPTBot,ClaudeBot"``). Leave empty for all agents.

        Returns:
            JSON with ``buckets`` (time-series data), ``agents`` (distinct
            agent names seen), and ``period``.
        """
        return _wrap(
            lambda c: c.get_traffic(site_id=site_id, period=period, agents=agents)
        )

    @mcp.tool()
    def list_toll_events(
        site_id: str,
        since: Optional[str] = None,
        until: Optional[str] = None,
        agent_name: Optional[str] = None,
        utm_source: Optional[str] = None,
        utm_medium: Optional[str] = None,
        utm_campaign: Optional[str] = None,
        utm_content: Optional[str] = None,
        utm_term: Optional[str] = None,
        request_host: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> str:
        """List individual tracked events for a Toll site, with filtering.

        Unlike ``get_toll_traffic`` (time-bucketed aggregate counts), this
        returns raw, row-level events — useful for inspecting specific
        traffic, campaign attribution, or every event in one session.

        Args:
            site_id: The site UUID.
            since: ISO 8601 timestamp — only events at or after this time.
                   Defaults to the last 7 days if omitted.
            until: ISO 8601 timestamp — only events at or before this time.
            agent_name: Comma-separated exact-match filter (e.g. "GPTBot,ClaudeBot").
            utm_source: Exact-match filter on the event's utm_source.
            utm_medium: Exact-match filter on the event's utm_medium.
            utm_campaign: Exact-match filter on the event's utm_campaign.
            utm_content: Exact-match filter on the event's utm_content.
            utm_term: Exact-match filter on the event's utm_term.
            request_host: Exact-match filter on the real hostname the request
                          arrived on — useful when a site is served under a
                          client's own domain via a reverse proxy and may
                          drift from the site's configured domain.
            session_id: Exact-match filter — all events belonging to one session.
            limit: Max rows to return (default 50, max 200).
            offset: Pagination offset.

        Returns:
            JSON with ``events`` (array of row-level event objects), ``total``
            (matching row count before pagination), ``limit``, ``offset``.
        """
        return _wrap(
            lambda c: c.list_events(
                site_id=site_id,
                since=since,
                until=until,
                agent_name=agent_name,
                utm_source=utm_source,
                utm_medium=utm_medium,
                utm_campaign=utm_campaign,
                utm_content=utm_content,
                utm_term=utm_term,
                request_host=request_host,
                session_id=session_id,
                limit=limit,
                offset=offset,
            )
        )
