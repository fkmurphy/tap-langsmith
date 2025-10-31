from singer_sdk import Tap, typing as th
from singer_sdk.streams import RESTStream
from typing import Optional, Any, Dict, Iterable
from datetime import datetime

ALLOWED_FIELDS = [
    "id", "name", "run_type", "start_time", "end_time", "status", "error", "extra", "events", "inputs",
    "inputs_preview", "inputs_s3_urls", "inputs_or_signed_url", "outputs", "outputs_preview", "outputs_s3_urls",
    "outputs_or_signed_url", "s3_urls", "error_or_signed_url", "events_or_signed_url", "extra_or_signed_url",
    "serialized_or_signed_url", "parent_run_id", "manifest_id", "manifest_s3_id", "manifest", "session_id",
    "serialized", "reference_example_id", "reference_dataset_id", "total_tokens", "prompt_tokens",
    "prompt_token_details", "completion_tokens", "completion_token_details", "total_cost", "prompt_cost",
    "prompt_cost_details", "completion_cost", "completion_cost_details", "price_model_id", "first_token_time",
    "trace_id", "dotted_order", "last_queued_at", "feedback_stats", "child_run_ids", "parent_run_ids",
    "tags", "in_dataset", "app_path", "share_token", "trace_tier", "trace_first_received_at", "ttl_seconds",
    "trace_upgrade", "thread_id", "trace_min_max_start_time"
]

class LangSmithStream(RESTStream):
    name = "query_runs"

    @property
    def replication_key(self) -> str:
        return "start_time"
    @replication_key.setter
    def replication_key(self, value: str) -> None:
        pass

    @property
    def is_sorted(self) -> bool:
        return False

    @property
    def url_base(self) -> str:
        return "https://api.smith.langchain.com"

    @property
    def schema(self) -> dict:
        # Solo define lo mínimo para no perder nada
        return th.PropertiesList(
            th.Property("start_time", th.DateTimeType, required=True),
            th.Property("trace_id", th.StringType, required=True),
            *(th.Property(f, th.AnyType()) for f in ALLOWED_FIELDS if f not in ("start_time", "trace_id"))
        ).to_dict()

    @property
    def path(self) -> str:
        return "/api/v1/runs/query"

    @property
    def rest_method(self) -> str:
        return "POST"

    @property
    def page_size(self) -> int:
        return 100

    @property
    def next_page_token_jsonpath(self) -> str:
        return "$.cursors.next"

    @property
    def http_headers(self) -> Dict[str, str]:
        return {
            "X-Api-Key": self.config["api_key"],
            "Content-Type": "application/json"
        }

    def prepare_request_payload(self, context: Optional[dict], next_page_token: Optional[Any]) -> dict:
        filter_str = "eq(is_root, true)"
        start_time = self.config.get("start_time")
        if start_time:
            try:
                dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                iso_ts = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                filter_str = f'and(eq(is_root, true), gte(start_time, "{iso_ts}"))'
            except Exception:
                pass

        payload = {
            "session": [self.config["session_id"]],
            "filter": filter_str,
            "limit": self.page_size,
            "select": ALLOWED_FIELDS
        }
        if next_page_token:
            payload["cursor"] = next_page_token
        else:
            payload["skip_prev_cursor"] = True

        return payload

    def parse_response(self, response) -> Iterable[dict]:
        return response.json().get("runs", [])

class LangSmithTap(Tap):
    name = "tap-langsmith"
    config_jsonschema = th.PropertiesList(
        th.Property("api_key", th.StringType, required=True, secret=True),
        th.Property("session_id", th.StringType, required=True),
        th.Property("start_time", th.StringType, required=False,
            description="Fecha inicio ISO8601 ej: 2025-11-01T00:46:00.512001Z")
    ).to_dict()

    def discover_streams(self):
        return [LangSmithStream(self)]

cli = LangSmithTap.cli
