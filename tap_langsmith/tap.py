from datetime import datetime, timedelta, timezone
from singer_sdk import Tap, typing as th
import time
from singer_sdk.streams import RESTStream

class LangSmithStream(RESTStream):
    name = "tap-langsmith"

    @property
    def replication_key(self) -> str:
        return "start_time"
    @replication_key.setter
    def replication_key(self, value: str) -> None:
        pass

    @property
    def is_sorted(self) -> bool:
        return True

    @property
    def url_base(self) -> str:
        return "https://api.smith.langchain.com"

    @property
    def schema(self) -> dict:
        return th.PropertiesList(
            th.Property("name", th.StringType, required=False, nullable=True),
            th.Property("inputs", th.ObjectType(additional_properties=True)),
            th.Property("inputs_preview", th.StringType, required=False, nullable=True),
            th.Property("run_type", th.StringType, required=False, nullable=True),
            th.Property("start_time", th.DateTimeType, required=True),
            th.Property("end_time", th.DateTimeType),
            th.Property("extra", th.ObjectType(additional_properties=True)),
            th.Property("error", th.StringType, required=False, nullable=True),
            th.Property("execution_order", th.NumberType, required=False, nullable=True),
            th.Property("outputs", th.ObjectType(additional_properties=True)),
            th.Property("outputs_preview", th.StringType, required=False, nullable=True),
            th.Property("events", th.ArrayType(th.ObjectType(additional_properties=True))),
            th.Property("parent_run_id", th.StringType, required=False, nullable=True),
            th.Property("tags", th.ArrayType(th.AnyType)),
            th.Property("trace_min_start_time", th.StringType, required=False, nullable=True),
            th.Property("trace_max_start_time", th.StringType, required=False, nullable=True),
            th.Property("id", th.StringType, required=False, nullable=True),
            th.Property("status", th.StringType, required=False, nullable=True),
            th.Property("trace_id", th.StringType, required=True),
            th.Property("child_run_ids", th.ArrayType(th.AnyType)),
            th.Property("feedback_stats", th.ObjectType(additional_properties=True)),
            th.Property("session_id", th.StringType, required=False, nullable=True),
            th.Property("total_tokens", th.NumberType),
            th.Property("prompt_tokens", th.NumberType),
            th.Property("prompt_token_details",th.ObjectType(additional_properties=True), required=False, nullable=True),
            th.Property("completion_tokens", th.NumberType),
            th.Property("completion_token_details",  th.ObjectType(additional_properties=True), required=False, nullable=True),
            th.Property("total_cost", th.NumberType),
            th.Property("prompt_cost", th.NumberType),
            th.Property("prompt_cost_details",  th.ObjectType(additional_properties=True), required=False, nullable=True),
            th.Property("completion_cost", th.NumberType),
            th.Property("completion_cost_details", th.ObjectType(additional_properties=True), required=False, nullable=True),
            th.Property("price_model_id", th.StringType, required=False, nullable=True),
            th.Property("first_token_time", th.DateTimeType),
            th.Property("ttl_seconds", th.NumberType),
            th.Property("thread_id", th.StringType, required=False, nullable=True),
        ).to_dict()

    @property
    def path(self) -> str:
        return "/api/v1/runs/query"
    @property
    def rest_method(self) -> str:
        return "POST"
    @property
    def page_size(self) -> int:
        return 80
    @property
    def next_page_token_jsonpath(self) -> str:
        return "$.cursors.next"
    @property
    def http_headers(self):
        return {
            "X-Api-Key": self.config["api_key"],
            "Content-Type": "application/json"
        }


    def _iso_utc(self, dt: datetime) -> str:
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _parse_iso(self, s: str) -> datetime:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    def _default_start_time(self) -> str:
        return self._iso_utc(datetime.now(timezone.utc) - timedelta(hours=36))

    def __init__(self, tap, name=None):
        super().__init__(tap, name)
        self._initial_bookmark = None

    def _get_initial_bookmark(self, context):
        ctx_state = self.get_context_state(context)
        bk = ctx_state.get("replication_key_value")

        if not bk:
            tap_state = self.tap_state or {}
            bookmarks = tap_state.get("bookmarks", {})
            stream_bk = bookmarks.get(self.name, {})
            self.logger.info(f"Setting bookmark - from tap state {stream_bk}")
            bk = stream_bk.get(self.replication_key)

        if not bk:
            conf_bk = self.config.get("start_time")
            if conf_bk:
                try:
                    bk = self._iso_utc(self._parse_iso(conf_bk))
                except:
                    self.logger.warning(f"Invalid start_time in config: {conf_bk}, falling back to -36h default")
                    bk = self._default_start_time()
            else:
                bk = self._default_start_time()
                self.logger.info(f"Setting bookmark - default to last 36h {bk}")

            self.logger.info(f"Setting bookmark - from config {bk}")

        self.logger.info(f"final bookmark set {bk}")

        return bk
    def prepare_request_payload(self, context, next_page_token):
        filter_str = "eq(is_root, true)"
        last_start_time = self.get_starting_replication_key_value(context)
        self.logger.info(f"Preparado filtros {self.tap_state} {last_start_time}")
        if self._initial_bookmark is None:
            self._initial_bookmark = self._get_initial_bookmark(context)
            self.logger.info(f"Initial bookmark for this run: {self._initial_bookmark}")

        filter_str = "eq(is_root, true)"
        if self._initial_bookmark:
            try:
                dt = self._parse_iso(str(self._initial_bookmark))
                iso_ts = self._iso_utc(dt)
                filter_str = f'and(eq(is_root, true), gte(start_time, "{iso_ts}"))'
            except Exception:
                self.logger.warning(f"Could not parse initial bookmark '{self._initial_bookmark}', using base filter only")
        payload = {
            "session": [self.config["session_id"]],
            "filter": filter_str,
            "limit": self.page_size,
            "order": "asc",
            "skip_pagination": False,
            "select":["id", "name", "run_type", "start_time", "end_time", "status", "error", "extra", "events", "inputs",
        "inputs_preview", "inputs_s3_urls", "inputs_or_signed_url", "outputs", "outputs_preview", "outputs_s3_urls",
        "outputs_or_signed_url", "s3_urls", "error_or_signed_url", "events_or_signed_url", "extra_or_signed_url",
        "serialized_or_signed_url", "parent_run_id", "session_id",
        "serialized", "reference_example_id", "reference_dataset_id", "total_tokens", "prompt_tokens",
        "prompt_token_details", "completion_tokens", "completion_token_details", "total_cost", "prompt_cost",
        "prompt_cost_details", "completion_cost", "completion_cost_details", "price_model_id", "first_token_time",
        "trace_id", "dotted_order", "last_queued_at", "feedback_stats", "child_run_ids", "parent_run_ids",
        "tags", "in_dataset", "app_path", "share_token", "trace_tier", "trace_first_received_at", "ttl_seconds",
        "trace_upgrade", "thread_id", "trace_min_max_start_time"]
        }
        if next_page_token:
            payload["cursor"] = next_page_token
        return payload

    def parse_response(self, response):
        results = response.json().get("runs", [])
        time.sleep(10)
        return results

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
