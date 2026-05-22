"""Basic unit tests for tap-langsmith.

These tests intentionally avoid hitting the LangSmith API. The intent is to
verify discovery, configuration validation, and the stream contract that the
Singer SDK exposes — the kind of thing a stale dependency would silently
break.
"""

from __future__ import annotations

import jsonschema
import pytest

from tap_langsmith.tap import LangSmithStream, LangSmithTap

SAMPLE_CONFIG = {
    "api_key": "lsv2_pt_fake_key_for_tests",
    "session_id": "00000000-0000-0000-0000-000000000000",
}


def test_tap_instantiates_with_minimum_config():
    tap = LangSmithTap(config=SAMPLE_CONFIG, parse_env_config=False)
    assert tap.name == "tap-langsmith"


def test_tap_config_jsonschema_requires_api_key_and_session_id():
    schema = LangSmithTap.config_jsonschema
    required = set(schema.get("required", []))
    assert "api_key" in required
    assert "session_id" in required


def test_config_validates_against_schema():
    schema = LangSmithTap.config_jsonschema
    jsonschema.validate(SAMPLE_CONFIG, schema)


def test_missing_required_config_fails_validation():
    schema = LangSmithTap.config_jsonschema
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"api_key": "x"}, schema)  # missing session_id


def test_discovery_returns_single_stream():
    tap = LangSmithTap(config=SAMPLE_CONFIG, parse_env_config=False)
    streams = tap.discover_streams()
    assert len(streams) == 1
    assert isinstance(streams[0], LangSmithStream)


def test_stream_declares_primary_key_and_replication():
    tap = LangSmithTap(config=SAMPLE_CONFIG, parse_env_config=False)
    stream = tap.discover_streams()[0]
    assert stream.primary_keys == ["id"]
    assert stream.replication_key == "start_time"
    assert stream.is_sorted is True


def test_stream_schema_is_valid_json_schema():
    tap = LangSmithTap(config=SAMPLE_CONFIG, parse_env_config=False)
    stream = tap.discover_streams()[0]
    schema = stream.schema
    # Will raise if the schema itself is malformed.
    jsonschema.Draft7Validator.check_schema(schema)
    # Sanity: must declare the keys we use downstream.
    properties = schema.get("properties", {})
    for required_field in ("id", "start_time", "trace_id", "total_tokens", "total_cost"):
        assert required_field in properties, f"missing column: {required_field}"


def test_catalog_emits_key_properties():
    """Singer schema messages must carry key_properties for upsert targets."""
    tap = LangSmithTap(config=SAMPLE_CONFIG, parse_env_config=False)
    catalog = tap.catalog_dict
    streams = catalog["streams"]
    assert len(streams) == 1
    assert streams[0]["key_properties"] == ["id"]
    assert streams[0]["replication_method"] == "INCREMENTAL"
