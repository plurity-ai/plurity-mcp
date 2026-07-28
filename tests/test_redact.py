"""The allow-lists in redact.py are the GDPR/DPA boundary for what reaches
the customer's LLM (DPA Q7/24) — these tests pin that boundary."""

from plurity_mcp.redact import (
    EVENT_FIELDS,
    SITE_FIELDS,
    pick,
    redact_events_response,
    redact_site_response,
)


SITE = {
    "id": "3f6d3f1a-0000-0000-0000-000000000000",
    "name": "Acme",
    "domain": "acme.com",
    "site_key": "stk_deadbeefdeadbeefdeadbeefdeadbeef",
    "llms_txt_mode": "manual",
    "cache_ttl_secs": 3600,
    "llms_preamble": None,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}

EVENT = {
    "id": "9a00c9a2-0000-0000-0000-000000000000",
    "occurred_at": "2026-07-01T12:00:00Z",
    "agent_name": "GPTBot",
    "page_url": "https://acme.com/pricing?session=abc123&email=a@b.com",
    "page_path": "/pricing",
    "http_method": "GET",
    "status_code": 200,
    "qa_pair_id": None,
    "custom_fields": {"internal_user_id": 42},
    "utm_source": "chatgpt",
    "utm_medium": None,
    "utm_campaign": "launch",
    "utm_content": None,
    "utm_term": None,
    "request_host": "acme.com",
    "country": "Germany",
    "country_code": "DE",
    "city": "Berlin",
    "latitude": 52.52,
    "longitude": 13.405,
    "converted": True,
}


def test_site_key_never_in_site_fields():
    assert "site_key" not in SITE_FIELDS


def test_pd_fields_never_in_event_fields():
    for banned in (
        "visitor_ip",
        "visitor_ip_hash",
        "user_agent",
        "referer",
        "session_id",
        "visitor_id",
        "latitude",
        "longitude",
        "custom_fields",
        "page_url",
    ):
        assert banned not in EVENT_FIELDS, banned


def test_redact_site_envelope_strips_site_key():
    out = redact_site_response({"site": SITE})
    assert "site_key" not in out["site"]
    assert out["site"]["id"] == SITE["id"]
    assert out["site"]["domain"] == "acme.com"


def test_redact_site_bare_object():
    out = redact_site_response(SITE)
    assert "site_key" not in out
    assert out["name"] == "Acme"


def test_redact_events_envelope():
    data = {"events": [EVENT], "total": 1, "limit": 50, "offset": 0}
    out = redact_events_response(data)
    assert out["total"] == 1 and out["limit"] == 50 and out["offset"] == 0
    (event,) = out["events"]
    assert set(event) <= EVENT_FIELDS
    for banned in ("latitude", "longitude", "custom_fields", "page_url"):
        assert banned not in event
    assert event["page_path"] == "/pricing"
    assert event["country_code"] == "DE"
    assert event["converted"] is True


def test_unexpected_shapes():
    # No events array — nothing to redact, envelope passes through untouched.
    assert redact_events_response({"error": "boom"}) == {"error": "boom"}
    # A bare dict is treated as a site object: whitelist strictness means
    # unknown keys are dropped, never leaked. (API errors raise inside _wrap
    # and never reach redaction, so nothing real is lost.)
    assert redact_site_response({"error": "boom"}) == {}
    assert pick("not-a-dict", SITE_FIELDS) == "not-a-dict"


def test_future_api_fields_are_dropped_by_default():
    out = redact_events_response({"events": [{**EVENT, "brand_new_field": 1}]})
    assert "brand_new_field" not in out["events"][0]
