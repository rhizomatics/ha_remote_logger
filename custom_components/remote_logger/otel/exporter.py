from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import aiohttp
from homeassistant.const import CONF_HEADERS, CONF_HOST, CONF_PATH, CONF_PORT, CONF_TOKEN
from homeassistant.const import __version__ as hass_version
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.remote_logger.const import (
    CONF_BATCH_MAX_SIZE,
    CONF_ENCODING,
    CONF_RESOURCE_ATTRIBUTES,
    CONF_USE_TLS,
    EVENT_SYSTEM_LOG,
)
from custom_components.remote_logger.exporter import LogExporter, LogMessage
from custom_components.remote_logger.helpers import flatten_event_data, isotimestamp

from .const import (
    CONF_TOKEN_TYPE,
    DEFAULT_RESOURCE_ATTRIBUTES,
    DEFAULT_SERVICE_NAME,
    DEFAULT_SEVERITY,
    ENCODING_JSON,
    ENCODING_PROTOBUF,
    OTLP_LOGS_PATH,
    SCOPE_NAME,
    SCOPE_VERSION,
    SEVERITY_MAP,
    TOKEN_TYPE_API_KEY,
    TOKEN_TYPE_BASIC,
    TOKEN_TYPE_BEARER,
    TOKEN_TYPE_RAW_BASIC,
)
from .protobuf_encoder import encode_export_logs_request

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import Event, HomeAssistant

_LOGGER = logging.getLogger(__name__)


def build_auth_header(token: str, token_type: str) -> str:
    """Build the Authorization header value for bearer or basic auth."""
    if token_type == TOKEN_TYPE_BASIC:
        credentials = base64.b64encode(token.encode()).decode()
        return f"Basic {credentials}"
    if token_type == TOKEN_TYPE_API_KEY:
        return f"ApiKey {token}"
    if token_type == TOKEN_TYPE_RAW_BASIC:
        return f"Basic {token}"
    return f"Bearer {token}"


def parse_resource_attributes(raw: str) -> list[tuple[str, str]]:
    """Parse 'key1=val1,key2=val2' into a list of (key, value) tuples.

    Raises ValueError if the format is invalid.
    """
    result = []
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise ValueError(f"Invalid attribute pair: {pair!r}")
        key, _, value = pair.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError("Attribute key cannot be empty")
        result.append((key, value))
    return result


def parse_headers(raw: str) -> dict[str, str]:
    """Parse 'Name: value' lines (newline-separated) into a dict.

    Raises ValueError if a line is malformed.
    """
    result: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"Invalid header line: {line!r}")
        name, _, value = line.partition(":")
        name = name.strip()
        if not name:
            raise ValueError("Header name cannot be empty")
        result[name] = value.strip()
    return result


def _kv(key: str, value: Any) -> dict[str, Any]:
    """Build an OTLP KeyValue attribute"""
    if isinstance(value, str):
        return {"key": key, "value": {"string_value": value}}
    if isinstance(value, bool):
        return {"key": key, "value": {"bool_value": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"int_value": value}}
    if isinstance(value, float):
        return {"key": key, "value": {"float_value": value}}
    if isinstance(value, bytes):
        return {"key": key, "value": {"byte_value": value}}
    return {"key": key, "value": {"string_value": str(value)}}


async def validate(
    session: aiohttp.ClientSession,
    url: str,
    encoding: str,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    # Validate connectivity
    errors: dict[str, str] = {}
    if encoding == ENCODING_PROTOBUF:
        data: bytes = encode_export_logs_request({"resourceLogs": []})
        content_type = "application/x-protobuf"
    elif encoding == ENCODING_JSON:
        data = json.dumps({"resourceLogs": []}).encode("utf-8")
        content_type = "application/json"
    else:
        raise ValueError(f"Unknown encoding {encoding}")
    headers = {"Content-Type": content_type, **(extra_headers or {})}
    try:
        async with session.post(
            url,
            data=data,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status >= 400 and resp.status < 500:
                errors["base"] = "cannot_connect"
                _LOGGER.error("OTEL-LOGS client connect failed (%s): %s", resp.status, await resp.text())
            if resp.status >= 500:
                errors["base"] = "cannot_connect"
                _LOGGER.error("OTEL-LOGS server connect failed (%s): %s", resp.status, await resp.text())
    except aiohttp.ClientResponseError as e1:
        errors["base"] = "cannot_connect"
        _LOGGER.error("OTEL-LOGS connect client response error: %s", e1)
    except aiohttp.ClientError as e2:
        errors["base"] = "cannot_connect"
        _LOGGER.error("OTEL-LOGS connect client error: %s", e2)
    except Exception as e3:
        errors["base"] = "unknown"
        _LOGGER.error("OTEL-LOGS connect unknown error: %s", e3)
    return errors


@dataclass
class OtlpMessage(LogMessage):
    payload: dict[str, Any]


class OtlpLogExporter(LogExporter):
    """Buffers system_log_event records and flushes them as OTLP/HTTP JSON."""

    logger_type = "otel"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass)
        self.name = entry.title

        self._in_progress: dict[str, Any] | None = None  # wrapped collection of OtlpMessages
        self._lock = asyncio.Lock()
        if hass and hass.config and hass.config.api:
            self.server_address = hass.config.api.local_ip
            self.server_port = hass.config.api.port
        else:
            self.server_address = None
            self.server_port = None

        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]
        encoding = entry.data[CONF_ENCODING]
        use_tls = entry.data[CONF_USE_TLS]
        scheme = "https" if use_tls else "http"
        path = entry.data.get(CONF_PATH, OTLP_LOGS_PATH)
        self.endpoint_url = f"{scheme}://{host}:{port}{path}"
        self.destination = (host, str(port), encoding)
        self._use_tls = use_tls
        self._use_protobuf = encoding == ENCODING_PROTOBUF
        self._entry = entry
        self._batch_max_size = entry.data.get(CONF_BATCH_MAX_SIZE, 100)
        self._extra_headers = self._build_extra_headers(entry)

        self._resource = self._build_resource(entry)

        _LOGGER.info(f"remote_logger: otel configured for {self.endpoint_url}, protobuf={self._use_protobuf}")

    def _build_extra_headers(self, entry: ConfigEntry) -> dict[str, str]:
        headers: dict[str, str] = {}
        token = entry.data.get(CONF_TOKEN, "").strip()
        if token:
            token_type = entry.data.get(CONF_TOKEN_TYPE, TOKEN_TYPE_BEARER)
            headers["Authorization"] = build_auth_header(token, token_type)
        raw_headers = entry.data.get(CONF_HEADERS, "").strip()
        if raw_headers:
            headers.update(parse_headers(raw_headers))
        return headers

    def _build_resource(self, entry: ConfigEntry) -> dict[str, Any]:
        """Build the OTLP Resource object with attributes."""
        attrs: list[dict[str, Any]] = [
            _kv("service.name", DEFAULT_SERVICE_NAME),
            _kv("service.version", hass_version or "unknown"),
        ]
        if self.server_address:
            attrs.append(_kv("service.address", self.server_address))
        if self.server_port:
            attrs.append(_kv("service.port", self.server_port))

        raw = entry.data.get(CONF_RESOURCE_ATTRIBUTES, DEFAULT_RESOURCE_ATTRIBUTES)
        if raw and raw.strip():
            for key, value in parse_resource_attributes(raw):
                attrs.append(_kv(key, value))

        return {"attributes": attrs}

    def _to_log_record(
        self,
        event: Event,
        message_override: list[str] | None = None,
        level_override: str | None = None,
        state_only: bool = False,
    ) -> OtlpMessage:
        """Convert a system_log_event payload to an OTLP logRecord dict."""
        """ HA System Log Event
            "name": str
            "message": list(str)
            "level": str
            "source": (str,int)
            "timestamp": float
            "exception": str
            "count": int
            "first_occurred": float
        """
        data = event.data or {}
        timestamp_s: float = data.get("timestamp", time.time())
        time_unix_nano = str(int(timestamp_s * 1_000_000_000))
        observed_timestamp: float = event.time_fired.timestamp()
        observed_time_unix_nano = str(int(observed_timestamp * 1_000_000_000))

        level: str = level_override or data.get("level", "INFO").upper()
        severity_number, severity_text = SEVERITY_MAP.get(level, DEFAULT_SEVERITY)

        messages: list[str] = message_override or data.get("message", [])
        message: str = "\n".join(messages)

        attributes: list[dict[str, Any]] = []

        if event.event_type == EVENT_SYSTEM_LOG:
            source = data.get("source")
            if source and isinstance(source, tuple):
                source_path, source_lineno = source
                attributes.append(_kv("code.file.path", source_path))
                attributes.append(_kv("code.line.number", source_lineno))
            logger_name = data.get("name")
            if data.get("count"):
                attributes.append(_kv("exception.count", data["count"]))
            if data.get("first_occurred"):
                attributes.append(_kv("exception.first_occurred", isotimestamp(data["first_occurred"])))
            if logger_name:
                attributes.append(_kv("code.function.name", logger_name))
            exception = data.get("exception")
            if exception:
                attributes.append(_kv("exception.stacktrace", exception))

        else:
            for k, v in data.items():
                for flat_key, flat_val in flatten_event_data(f"event.data.{k}" if k != "event.data" else k, v, state_only):
                    attributes.append(_kv(flat_key, flat_val))

        # https://github.com/open-telemetry/opentelemetry-proto/blob/main/opentelemetry/proto/logs/v1/logs.proto
        return OtlpMessage(
            payload={
                "timeUnixNano": time_unix_nano,
                "observedTimeUnixNano": observed_time_unix_nano,
                "severityNumber": severity_number,
                "severityText": severity_text,
                "body": {"string_value": message},
                "attributes": attributes,
                "eventName": event.event_type if event != EVENT_SYSTEM_LOG else None,
            }
        )

    def generate_submission(self, records: list[OtlpMessage]) -> dict[str, Any]:
        request = self._build_export_request(records)
        if self._use_protobuf:
            content_type = "application/x-protobuf"
            result: dict[str, Any] = {"data": encode_export_logs_request(request)}
        else:
            content_type = "application/json"
            result = {"json": request}
        result["headers"] = {"Content-Type": content_type, **self._extra_headers}
        return result

    async def flush(self) -> None:
        """Flush all buffered log records to the OTLP endpoint."""
        records: list[OtlpMessage] | None = None
        async with self._lock:
            if not self._in_progress:
                if not self._buffer:
                    return
                records = cast("list[OtlpMessage]", self._buffer.copy())
                self._buffer.clear()

        try:
            if records and not self._in_progress:
                msg: dict[str, Any] = self.generate_submission(records)
            elif self._in_progress:
                msg = self._in_progress
            else:
                return
            session: aiohttp.ClientSession = async_get_clientsession(self._hass, verify_ssl=self._use_tls)
            async with session.post(self.endpoint_url, timeout=aiohttp.ClientTimeout(total=10), **msg) as resp:
                if resp.status in (401, 403):
                    _LOGGER.warning("remote_logger: OTLP authentication failed (%s), triggering reauth", resp.status)
                    self._in_progress = None
                    self._entry.async_start_reauth(self._hass)
                    return
                if resp.status >= 400:
                    body = await resp.text()
                    _LOGGER.warning(
                        "remote_logger: OTLP endpoint returned HTTP %s: %s",
                        resp.status,
                        body[:200],
                    )
                    self.on_posting_error(body)
                if resp.ok or (resp.status >= 400 and resp.status < 500):
                    # records were sent, or there was a client-side error
                    self._in_progress = None
                    self.on_success()

        except aiohttp.ClientError as err:
            _LOGGER.warning("remote_logger: failed to send logs: %s", err)
            self.on_posting_error(str(err))
        except Exception as e:
            _LOGGER.exception("remote_logger: unexpected error sending logs, skipping records")
            self.on_posting_error(str(e))
            self._in_progress = None

    def log_direct(self, event_name: str, message: str, level: str, attributes: dict[str, Any] | None = None) -> None:
        """Buffer a custom log record without requiring a HA Event."""
        now = time.time()
        time_unix_nano = str(int(now * 1_000_000_000))
        severity_number, severity_text = SEVERITY_MAP.get(level.upper(), DEFAULT_SEVERITY)
        attrs = [_kv(k, v) for k, v in (attributes or {}).items()]
        record = OtlpMessage(
            payload={
                "timeUnixNano": time_unix_nano,
                "observedTimeUnixNano": time_unix_nano,
                "severityNumber": severity_number,
                "severityText": severity_text,
                "body": {"string_value": message},
                "attributes": attrs,
                "eventName": event_name,
            }
        )
        self._buffer.append(record)
        self.on_event()
        if len(self._buffer) >= self._batch_max_size:
            self._hass.async_create_task(self.flush())

    def _build_export_request(self, records: list[OtlpMessage]) -> dict[str, Any]:
        """Wrap logRecords in the ExportLogsServiceRequest envelope."""
        return {
            "resourceLogs": [
                {
                    "resource": self._resource,
                    "scopeLogs": [
                        {
                            "scope": {
                                "name": SCOPE_NAME,
                                "version": SCOPE_VERSION,
                            },
                            "logRecords": [r.payload for r in records],
                        }
                    ],
                }
            ],
        }
