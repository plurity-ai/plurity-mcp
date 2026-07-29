"""Field allow-lists applied to API responses before they reach the LLM.

The REST API is authenticated with the org's own ``plt_`` key, so it may
return fields we do not want forwarded into a model context — the ``stk_``
site key, per-event coordinates, arbitrary ``custom_fields`` JSON, full URLs
with query strings. Tools whitelist here rather than blocklist so that new
API fields stay out of LLM context until explicitly reviewed (DPA Q7/24).
"""

from __future__ import annotations

from typing import Any

# Site details, minus site_key. The key is intentionally public on the
# customer's own pages (script tag, ?key= links), but it must not be echoed
# into LLM context — get_toll_installation_instructions is the one tool that
# hands it out, on purpose.
SITE_FIELDS = frozenset(
    {
        "id",
        "name",
        "domain",
        "llms_txt_mode",
        "cache_ttl_secs",
        "llms_preamble",
        "created_at",
        "updated_at",
    }
)

# Row-level events, minus latitude/longitude (finer than the "coarse geo" the
# tool promises), custom_fields (arbitrary customer-supplied JSON), and
# page_url (full URL incl. query strings — page_path is the normalized form).
EVENT_FIELDS = frozenset(
    {
        "id",
        "occurred_at",
        "agent_name",
        "page_path",
        "http_method",
        "status_code",
        "qa_pair_id",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "request_host",
        "country",
        "country_code",
        "city",
        "converted",
    }
)


def pick(obj: Any, fields: frozenset[str]) -> Any:
    """Return *obj* with only the allow-listed keys (non-dicts pass through)."""
    if not isinstance(obj, dict):
        return obj
    return {k: v for k, v in obj.items() if k in fields}


def redact_site_response(data: Any) -> Any:
    """Redact a ``{"site": {...}}`` envelope (get/create/update site)."""
    if isinstance(data, dict) and isinstance(data.get("site"), dict):
        return {**data, "site": pick(data["site"], SITE_FIELDS)}
    return pick(data, SITE_FIELDS)


def redact_events_response(data: Any) -> Any:
    """Redact an ``{"events": [...], "total": ...}`` envelope."""
    if isinstance(data, dict) and isinstance(data.get("events"), list):
        return {
            **data,
            "events": [pick(e, EVENT_FIELDS) for e in data["events"]],
        }
    return data
