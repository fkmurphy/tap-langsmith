"""Unit tests for the parts of the tap that actually broke in production.

Each test exercises one named branch in `tap.py`:
    - `_build_filter`     — base filter + bookmark composition
    - `_get_initial_bookmark` — context state -> tap_state -> config -> default
    - `prepare_request_payload` — payload structure and pagination cursor
    - `parse_response` — the configurable rate-limit delay

We instantiate the stream directly and drive its methods. The HTTP layer is
faked with a `unittest.mock.Mock` only where strictly necessary (parse_response,
which calls `response.json()`).

These do NOT test what `singer-sdk` already covers (pagination loop, state
persistence) — we trust the SDK there.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from tap_langsmith.tap import (
    DEFAULT_LOOKBACK_HOURS,
    DEFAULT_REQUEST_DELAY_SECONDS,
    LangSmithStream,
    LangSmithTap,
)

MINIMAL_CONFIG = {
    "api_key": "lsv2_pt_fake",
    "session_id": "00000000-0000-0000-0000-000000000000",
}


def _stream(extra_config: dict | None = None) -> LangSmithStream:
    cfg = {**MINIMAL_CONFIG, **(extra_config or {})}
    tap = LangSmithTap(config=cfg, parse_env_config=False)
    return tap.discover_streams()[0]


# ---------------------------------------------------------------------------
# _build_filter
# ---------------------------------------------------------------------------

class TestBuildFilter:
    def test_default_no_bookmark_returns_is_root(self):
        s = _stream()
        assert s._build_filter(None) == "eq(is_root, true)"

    def test_default_with_bookmark_ands_clauses(self):
        s = _stream()
        bk = "2026-01-15T00:00:00Z"
        assert s._build_filter(bk) == f'and(eq(is_root, true), gte(start_time, "{bk}"))'

    def test_is_root_only_false_drops_base_filter(self):
        s = _stream({"is_root_only": False})
        assert s._build_filter(None) == ""

    def test_is_root_only_false_with_bookmark_emits_only_replication_clause(self):
        s = _stream({"is_root_only": False})
        bk = "2026-01-15T00:00:00Z"
        assert s._build_filter(bk) == f'gte(start_time, "{bk}")'

    def test_custom_filter_replaces_default(self):
        s = _stream({"filter": 'eq(status, "error")'})
        assert s._build_filter(None) == 'eq(status, "error")'

    def test_custom_filter_combined_with_bookmark(self):
        s = _stream({"filter": 'eq(status, "error")'})
        bk = "2026-01-15T00:00:00Z"
        assert s._build_filter(bk) == f'and(eq(status, "error"), gte(start_time, "{bk}"))'

    def test_custom_filter_overrides_is_root_only(self):
        """When `filter` is explicitly set, `is_root_only` is ignored."""
        s = _stream({"filter": 'eq(status, "error")', "is_root_only": True})
        assert "is_root" not in s._build_filter(None)


# ---------------------------------------------------------------------------
# _get_initial_bookmark
# ---------------------------------------------------------------------------

class TestInitialBookmark:
    def test_uses_context_state_when_present(self):
        s = _stream()
        with patch.object(s, "get_context_state", return_value={"replication_key_value": "ctx-value"}):
            assert s._get_initial_bookmark(context=None) == "ctx-value"

    def test_falls_back_to_tap_state_bookmarks(self):
        s = _stream()
        with patch.object(s, "get_context_state", return_value={}), \
             patch.object(LangSmithStream, "tap_state", new={"bookmarks": {"tap-langsmith": {"start_time": "tap-state-value"}}}):
            assert s._get_initial_bookmark(context=None) == "tap-state-value"

    def test_falls_back_to_start_time_config(self):
        s = _stream({"start_time": "2025-12-01T00:00:00Z"})
        with patch.object(s, "get_context_state", return_value={}), \
             patch.object(LangSmithStream, "tap_state", new={}):
            assert s._get_initial_bookmark(context=None) == "2025-12-01T00:00:00Z"

    def test_invalid_start_time_falls_back_to_lookback(self):
        s = _stream({"start_time": "not-a-date"})
        with patch.object(s, "get_context_state", return_value={}), \
             patch.object(LangSmithStream, "tap_state", new={}), \
             patch.object(s, "_default_start_time", return_value="lookback-default"):
            assert s._get_initial_bookmark(context=None) == "lookback-default"

    def test_no_state_no_config_uses_default_lookback(self):
        s = _stream()
        with patch.object(s, "get_context_state", return_value={}), \
             patch.object(LangSmithStream, "tap_state", new={}), \
             patch.object(s, "_default_start_time", return_value="LOOKBACK"):
            assert s._get_initial_bookmark(context=None) == "LOOKBACK"

    def test_default_lookback_honors_config_hours(self):
        from datetime import datetime, timedelta, timezone
        s = _stream({"lookback_hours": 24})
        result = s._default_start_time()
        # Should be within 1 minute of now-24h.
        expected = datetime.now(timezone.utc) - timedelta(hours=24)
        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
        diff = abs((parsed - expected).total_seconds())
        assert diff < 60, f"expected ~now-24h, got {result} (diff {diff}s)"

    def test_default_lookback_uses_default_when_unset(self):
        from datetime import datetime, timedelta, timezone
        s = _stream()
        result = s._default_start_time()
        expected = datetime.now(timezone.utc) - timedelta(hours=DEFAULT_LOOKBACK_HOURS)
        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert abs((parsed - expected).total_seconds()) < 60


# ---------------------------------------------------------------------------
# prepare_request_payload
# ---------------------------------------------------------------------------

class TestRequestPayload:
    def _payload(self, stream, next_token=None, bookmark="2026-01-15T00:00:00Z"):
        # Bypass _get_initial_bookmark for deterministic input.
        stream._initial_bookmark = bookmark
        with patch.object(stream, "get_starting_replication_key_value", return_value=bookmark):
            return stream.prepare_request_payload(context=None, next_page_token=next_token)

    def test_payload_includes_required_fields(self):
        s = _stream()
        payload = self._payload(s)
        for key in ("session", "filter", "limit", "order", "skip_pagination", "select"):
            assert key in payload, f"payload missing key: {key}"

    def test_payload_session_uses_config(self):
        s = _stream({"session_id": "deadbeef-cafe-babe-dead-beefcafebabe"})
        payload = self._payload(s)
        assert payload["session"] == ["deadbeef-cafe-babe-dead-beefcafebabe"]

    def test_payload_limit_matches_page_size(self):
        s = _stream({"page_size": 25})
        payload = self._payload(s)
        assert payload["limit"] == 25

    def test_payload_order_is_asc(self):
        s = _stream()
        payload = self._payload(s)
        assert payload["order"] == "asc"

    def test_payload_filter_combines_bookmark_when_present(self):
        s = _stream()
        payload = self._payload(s, bookmark="2026-01-15T00:00:00Z")
        assert "gte(start_time" in payload["filter"]
        assert "eq(is_root, true)" in payload["filter"]

    def test_cursor_added_when_paginating(self):
        s = _stream()
        payload = self._payload(s, next_token="some-cursor")
        assert payload["cursor"] == "some-cursor"

    def test_no_cursor_on_first_page(self):
        s = _stream()
        payload = self._payload(s, next_token=None)
        assert "cursor" not in payload

    def test_select_contains_critical_columns(self):
        """If LangSmith ever drops a column from the select list, downstream
        consumers (Postgres tables, Grafana queries) start emitting nulls."""
        s = _stream()
        payload = self._payload(s)
        for col in ("id", "trace_id", "start_time", "total_tokens", "total_cost", "thread_id"):
            assert col in payload["select"], f"select missing critical column: {col}"


# ---------------------------------------------------------------------------
# parse_response
# ---------------------------------------------------------------------------

class TestParseResponse:
    def _mock_response(self, runs):
        m = Mock()
        m.json.return_value = {"runs": runs}
        return m

    def test_extracts_runs_array(self):
        s = _stream({"request_delay_seconds": 0})  # no sleep during tests
        sample = [{"id": "r1"}, {"id": "r2"}]
        assert s.parse_response(self._mock_response(sample)) == sample

    def test_returns_empty_list_when_no_runs(self):
        s = _stream({"request_delay_seconds": 0})
        m = Mock()
        m.json.return_value = {}  # API returned no runs key
        assert s.parse_response(m) == []

    def test_zero_delay_skips_sleep(self):
        s = _stream({"request_delay_seconds": 0})
        with patch("tap_langsmith.tap.time.sleep") as sleep_mock:
            s.parse_response(self._mock_response([]))
            sleep_mock.assert_not_called()

    def test_default_delay_applies_sleep(self):
        s = _stream()
        with patch("tap_langsmith.tap.time.sleep") as sleep_mock:
            s.parse_response(self._mock_response([]))
            sleep_mock.assert_called_once_with(float(DEFAULT_REQUEST_DELAY_SECONDS))

    def test_custom_delay_passed_to_sleep(self):
        s = _stream({"request_delay_seconds": 2.5})
        with patch("tap_langsmith.tap.time.sleep") as sleep_mock:
            s.parse_response(self._mock_response([]))
            sleep_mock.assert_called_once_with(2.5)


# ---------------------------------------------------------------------------
# Stream-level config wiring
# ---------------------------------------------------------------------------

class TestStreamConfig:
    def test_url_base_default(self):
        s = _stream()
        assert s.url_base == "https://api.smith.langchain.com"

    def test_url_base_can_be_overridden(self):
        s = _stream({"api_url": "https://langsmith.internal.example.com"})
        assert s.url_base == "https://langsmith.internal.example.com"

    def test_page_size_default(self):
        assert _stream().page_size == 80

    def test_page_size_can_be_overridden(self):
        assert _stream({"page_size": 200}).page_size == 200

    def test_http_headers_carry_api_key(self):
        s = _stream({"api_key": "lsv2_pt_specific"})
        headers = s.http_headers
        assert headers["X-Api-Key"] == "lsv2_pt_specific"
        assert headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# Regression guard for PR #1 (primary_keys ausente causaba duplicación)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("attr,expected", [
    ("primary_keys", ["id"]),
    ("replication_key", "start_time"),
    ("is_sorted", True),
])
def test_stream_critical_attributes(attr, expected):
    """If any of these change silently, the upsert path in target-postgres
    breaks (the very bug PR #1 fixed)."""
    s = _stream()
    assert getattr(s, attr) == expected
