"""Synchronous HTTP clients for each Plurity service.

All clients share the same auth header (Bearer plt_*) and error model
(:class:`PlurityAPIError`). Service-specific methods live on each subclass.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx

_DEFAULT_TIMEOUT = 30.0


class PlurityAPIError(Exception):
    """Raised when a Plurity service returns an error response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class _BaseClient:
    """Shared httpx wrapper used by all service clients."""

    def __init__(self, api_key: str, base_url: str, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=timeout,
        )

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.is_success:
            return
        try:
            body = response.json()
            detail = body.get("error") or body.get("message") or body.get("detail", "")
        except Exception:
            detail = response.text or "(no body)"
        raise PlurityAPIError(
            f"API error {response.status_code}: {detail}",
            status_code=response.status_code,
        )

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        response = self._client.get(
            path, params={k: v for k, v in params.items() if v is not None}
        )
        self._raise_for_status(response)
        return response.json()

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(path, json=body)
        self._raise_for_status(response)
        return response.json()

    def _patch(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        response = self._client.patch(path, json=body)
        self._raise_for_status(response)
        return response.json()

    def _delete(self, path: str, **params: Any) -> dict[str, Any]:
        response = self._client.delete(
            path, params={k: v for k, v in params.items() if v is not None}
        )
        self._raise_for_status(response)
        return response.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "_BaseClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Audit client
# ---------------------------------------------------------------------------


class AuditClient(_BaseClient):
    """Client for the Plurity GEO Audit API."""

    def submit_scan(self, url: str, webhook_url: str = "") -> dict[str, Any]:
        body: dict[str, Any] = {"url": url}
        if webhook_url:
            body["webhook_url"] = webhook_url
        return self._post("/api/v1/scans", body)

    def get_scan(self, scan_id: str) -> dict[str, Any]:
        return self._get(f"/api/v1/scans/{scan_id}")

    def get_scan_by_url(self, url: str) -> dict[str, Any]:
        return self._get("/api/v1/scans", url=url)

    def wait_for_scan(
        self,
        scan_id: str,
        timeout_seconds: int = 300,
        poll_interval: float = 5.0,
    ) -> dict[str, Any]:
        _TERMINAL = {"complete", "failed"}
        deadline = time.monotonic() + timeout_seconds
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last = self.get_scan(scan_id)
            if last.get("status") in _TERMINAL:
                return last
            remaining = deadline - time.monotonic()
            time.sleep(min(poll_interval, max(remaining, 0)))
        return last


# ---------------------------------------------------------------------------
# Toll client
# ---------------------------------------------------------------------------


class TollClient(_BaseClient):
    """Client for the Plurity Toll API (agent traffic + llms.txt management)."""

    # Sites
    def list_sites(self) -> dict[str, Any]:
        return self._get("/api/v1/sites")

    def create_site(self, name: str, domain: str) -> dict[str, Any]:
        return self._post("/api/v1/sites", {"name": name, "domain": domain})

    def get_site(self, site_id: str) -> dict[str, Any]:
        return self._get(f"/api/v1/sites/{site_id}")

    def update_site(
        self,
        site_id: str,
        name: Optional[str] = None,
        domain: Optional[str] = None,
        cache_ttl_secs: Optional[int] = None,
        llms_txt_mode: Optional[str] = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if domain is not None:
            body["domain"] = domain
        if cache_ttl_secs is not None:
            body["cache_ttl_secs"] = cache_ttl_secs
        if llms_txt_mode is not None:
            body["llms_txt_mode"] = llms_txt_mode
        return self._patch(f"/api/v1/sites/{site_id}", body)

    # Q&A pairs
    def list_qa_pairs(self, site_id: str) -> dict[str, Any]:
        return self._get(f"/api/v1/sites/{site_id}/qa-pairs")

    def create_qa_pair(
        self,
        site_id: str,
        question: str,
        answer_url: str,
        answer_summary: Optional[str] = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"question": question, "answer_url": answer_url}
        if answer_summary is not None:
            body["answer_summary"] = answer_summary
        return self._post(f"/api/v1/sites/{site_id}/qa-pairs", body)

    def update_qa_pair(
        self,
        site_id: str,
        pair_id: str,
        question: Optional[str] = None,
        answer_url: Optional[str] = None,
        answer_summary: Optional[str] = None,
        is_published: Optional[bool] = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if question is not None:
            body["question"] = question
        if answer_url is not None:
            body["answer_url"] = answer_url
        if answer_summary is not None:
            body["answer_summary"] = answer_summary
        if is_published is not None:
            body["is_published"] = is_published
        return self._patch(f"/api/v1/sites/{site_id}/qa-pairs/{pair_id}", body)

    def delete_qa_pair(self, site_id: str, pair_id: str) -> dict[str, Any]:
        return self._delete(f"/api/v1/sites/{site_id}/qa-pairs/{pair_id}")

    # Traffic
    def get_traffic(
        self,
        site_id: str,
        period: str = "week",
        agents: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._get(
            f"/api/v1/sites/{site_id}/events/chart",
            period=period,
            agents=agents,
        )


# ---------------------------------------------------------------------------
# Intelligence client
# ---------------------------------------------------------------------------


class IntelligenceClient(_BaseClient):
    """Client for the Plurity Intelligence API (question + topic monitoring)."""

    # Sources
    def list_sources(
        self,
        type: Optional[str] = None,
        q: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._get("/api/v1/sources", type=type, q=q)

    def list_subscriptions(self) -> dict[str, Any]:
        return self._get("/api/v1/subscriptions")

    def subscribe_source(
        self,
        source_id: str,
        start_date: Optional[str] = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if start_date is not None:
            body["start_date"] = start_date
        return self._post(f"/api/v1/sources/{source_id}/subscribe", body)

    def unsubscribe_source(self, source_id: str) -> dict[str, Any]:
        return self._delete(f"/api/v1/sources/{source_id}/subscribe")

    def request_source(self, url: str) -> dict[str, Any]:
        return self._post("/api/v1/sources/request", {"url": url})

    # Source content (documents)
    def list_source_content(
        self,
        source_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._get(
            "/api/v1/source-content",
            source_id=source_id,
            date_from=date_from,
            date_to=date_to,
            content_type=content_type,
        )

    # Q&A feed
    def list_qa_pairs(
        self,
        source_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._get(
            "/api/v1/feed",
            source_id=source_id,
            date_from=date_from,
            date_to=date_to,
            status=status,
        )

    def approve_qa_pair(self, qa_pair_id: str) -> dict[str, Any]:
        return self._post(f"/api/v1/feed/{qa_pair_id}/approve", {})

    def skip_qa_pair(self, qa_pair_id: str) -> dict[str, Any]:
        return self._post(f"/api/v1/feed/{qa_pair_id}/skip", {})
