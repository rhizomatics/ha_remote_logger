"""Unit tests for the OTEL exporter."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from homeassistant.core import Event

from custom_components.remote_logger.otel.exporter import (
    OtlpLogExporter,
    OtlpMessage,
    _kv,
    build_auth_header,
    parse_resource_attributes,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# ---------------------------------------------------------------------------
# build_auth_header
# ---------------------------------------------------------------------------


class TestBuildAuthHeader:
    def test_bearer(self) -> None:
        assert build_auth_header("mytoken", "bearer") == "Bearer mytoken"

    def test_basic(self) -> None:
        import base64

        expected = "Basic " + base64.b64encode(b"user:pass").decode()
        assert build_auth_header("user:pass", "basic") == expected

    def test_unknown_type_falls_back_to_bearer(self) -> None:
        assert build_auth_header("tok", "other") == "Bearer tok"


# ---------------------------------------------------------------------------
# parse_resource_attributes
# ---------------------------------------------------------------------------


class TestParseResourceAttributes:
    def test_simple_pair(self) -> None:
        assert parse_resource_attributes("env=prod") == [("env", "prod")]

    def test_multiple_pairs(self) -> None:
        result = parse_resource_attributes("env=prod,region=us-east-1")
        assert result == [("env", "prod"), ("region", "us-east-1")]

    def test_whitespace_handling(self) -> None:
        result = parse_resource_attributes("  env = prod , region = us-east-1  ")
        assert result == [("env", "prod"), ("region", "us-east-1")]

    def test_empty_string(self) -> None:
        assert parse_resource_attributes("") == []

    def test_blank_string(self) -> None:
        assert parse_resource_attributes("   ") == []

    def test_trailing_comma(self) -> None:
        assert parse_resource_attributes("env=prod,") == [("env", "prod")]

    def test_value_with_equals(self) -> None:
        result = parse_resource_attributes("key=val=ue")
        assert result == [("key", "val=ue")]

    def test_empty_value(self) -> None:
        result = parse_resource_attributes("key=")
        assert result == [("key", "")]

    def test_missing_equals_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid attribute pair"):
            parse_resource_attributes("no_equals_sign")

    def test_empty_key_raises(self) -> None:
        with pytest.raises(ValueError, match="key cannot be empty"):
            parse_resource_attributes("=value")


# ---------------------------------------------------------------------------
# _kv helper
# ---------------------------------------------------------------------------


class TestKv:
    def test_string_value(self) -> None:
        assert _kv("key", "val") == {"key": "key", "value": {"string_value": "val"}}

    def test_int_value(self) -> None:
        assert _kv("key", 42) == {"key": "key", "value": {"int_value": 42}}

    def test_bool_value(self) -> None:
        assert _kv("key", True) == {"key": "key", "value": {"bool_value": True}}

    def test_float_value(self) -> None:
        assert _kv("key", 3.14) == {"key": "key", "value": {"float_value": 3.14}}

    def test_bytes_value(self) -> None:
        assert _kv("key", b"data") == {"key": "key", "value": {"byte_value": b"data"}}

    def test_other_value_becomes_string(self) -> None:
        result = _kv("key", [1, 2, 3])
        assert result == {"key": "key", "value": {"string_value": "[1, 2, 3]"}}


# ---------------------------------------------------------------------------
# OtlpLogExporter
# ---------------------------------------------------------------------------


class TestOtlpLogExporter:
    @pytest.fixture
    def exporter(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> OtlpLogExporter:
        return OtlpLogExporter(hass, mock_entry_otel)

    @pytest.fixture
    def exporter_with_attrs(self, hass: HomeAssistant, mock_entry_otel_protobuf: MagicMock) -> OtlpLogExporter:
        return OtlpLogExporter(hass, mock_entry_otel_protobuf)

    def test_extra_headers_bearer(self, hass: HomeAssistant) -> None:
        entry = MagicMock()
        entry.data = {
            "host": "localhost",
            "port": 4318,
            "use_tls": False,
            "encoding": "json",
            "batch_max_size": 20,
            "resource_attributes": "",
            "token": "mytoken",
            "token_type": "bearer",
        }
        exp = OtlpLogExporter(hass, entry)
        assert exp._extra_headers["Authorization"] == "Bearer mytoken"

    def test_extra_headers_basic(self, hass: HomeAssistant) -> None:
        import base64

        entry = MagicMock()
        entry.data = {
            "host": "localhost",
            "port": 4318,
            "use_tls": False,
            "encoding": "json",
            "batch_max_size": 20,
            "resource_attributes": "",
            "token": "user:pass",
            "token_type": "basic",
        }
        exp = OtlpLogExporter(hass, entry)
        expected = "Basic " + base64.b64encode(b"user:pass").decode()
        assert exp._extra_headers["Authorization"] == expected

    def test_extra_headers_no_token(self, exporter: OtlpLogExporter) -> None:
        assert "Authorization" not in exporter._extra_headers

    def test_name_from_entry_title(self, exporter: OtlpLogExporter) -> None:
        assert exporter.name == "OTel Remote Logger"

    def test_endpoint_url_http(self, exporter: OtlpLogExporter) -> None:
        assert exporter.endpoint_url == "http://localhost:4318/v1/logs"

    def test_endpoint_url_https(self, hass: HomeAssistant) -> None:
        entry = MagicMock()
        entry.data = {
            "host": "otel.example.com",
            "port": 443,
            "use_tls": True,
            "encoding": "json",
            "batch_max_size": 20,
            "resource_attributes": "",
        }
        exp = OtlpLogExporter(hass, entry)
        assert exp.endpoint_url == "https://otel.example.com:443/v1/logs"

    def test_resource_has_service_name(self, exporter: OtlpLogExporter) -> None:
        attrs = exporter._resource["attributes"]
        keys = [a["key"] for a in attrs]
        assert "service.name" in keys
        assert "service.version" in keys

    def test_resource_custom_attributes(self, exporter_with_attrs: OtlpLogExporter) -> None:
        attrs = exporter_with_attrs._resource["attributes"]
        keys = [a["key"] for a in attrs]
        assert "env" in keys
        assert "region" in keys

    def test_to_log_record_full(self, exporter: OtlpLogExporter, sample_log_event: Event) -> None:
        record: OtlpMessage = exporter._to_log_record(sample_log_event)

        assert record.payload["severityNumber"] == 17
        assert record.payload["severityText"] == "ERROR"
        assert record.payload["body"] == {"string_value": "Something went wrong"}
        assert "timeUnixNano" in record.payload
        assert "observedTimeUnixNano" in record.payload

        attr_keys = [a["key"] for a in record.payload["attributes"]]
        assert "code.file.path" in attr_keys
        assert "code.line.number" in attr_keys
        assert "code.function.name" in attr_keys
        assert "exception.stacktrace" in attr_keys
        assert "exception.count" in attr_keys
        assert "exception.first_occurred" in attr_keys

    def test_to_log_record_minimal(self, exporter: OtlpLogExporter, minimal_log_event: Event) -> None:
        record = exporter._to_log_record(minimal_log_event)

        assert record.payload["severityNumber"] == 9
        assert record.payload["severityText"] == "INFO"
        assert record.payload["body"] == {"string_value": "Simple info message"}
        # No source, name, exception attributes
        assert record.payload["attributes"] == []

    def test_to_log_record_unknown_level(self, exporter: OtlpLogExporter) -> None:
        record = exporter._to_log_record(Event("system_log_event", data={"level": "TRACE", "message": ["test"]}))
        # Falls back to default severity (INFO)
        assert record.payload["severityNumber"] == 9
        assert record.payload["severityText"] == "INFO"

    def test_to_log_record_multiple_messages(self, exporter: OtlpLogExporter) -> None:
        record = exporter._to_log_record(Event("system_log_event", data={"message": ["line 1", "line 2", "line 3"]}))
        assert record.payload["body"]["string_value"] == "line 1\nline 2\nline 3"

    def test_to_protobuf(self, exporter: OtlpLogExporter, sample_log_event: Event) -> None:
        record = exporter._to_log_record(sample_log_event)
        exporter._use_protobuf = True
        result = exporter.generate_submission([record])
        assert result["data"] is not None
        assert isinstance(result["data"], bytes)
        assert len(result["data"]) > 400

    def test_to_json(self, exporter: OtlpLogExporter, sample_log_event: Event) -> None:
        record = exporter._to_log_record(sample_log_event)
        exporter._use_protobuf = False
        result = exporter.generate_submission([record])
        body = result["json"]
        resource_attrs = {a["key"]: a["value"] for a in body["resourceLogs"][0]["resource"]["attributes"]}
        assert resource_attrs["service.name"]["string_value"] == "homeassistant.core"
        log_record = body["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]
        assert log_record["timeUnixNano"] == "1700000000000000000"

    def test_handle_event_buffers(self, exporter: OtlpLogExporter, mock_event: MagicMock) -> None:
        assert len(exporter._buffer) == 0
        exporter.handle_event(mock_event)
        assert len(exporter._buffer) == 1

    def test_handle_event_loop_check_(self, exporter: OtlpLogExporter) -> None:
        """Tuple `in` check doesn't do substring matching on elements."""
        event = MagicMock()
        event.data = {
            "message": ["some otel error"],
            "level": "ERROR",
            "source": ("custom_components/remote_logger/otel/exporter.py", 100),
        }
        exporter.handle_event(event)
        assert len(exporter._buffer) == 0

    def test_handle_event_allows_non_otel_source(self, exporter: OtlpLogExporter) -> None:
        event = MagicMock()
        event.data = {
            "message": ["some error"],
            "level": "ERROR",
            "source": ("homeassistant/core.py", 50),
        }
        exporter.handle_event(event)
        assert len(exporter._buffer) == 1

    def test_build_export_request_structure(self, exporter: OtlpLogExporter) -> None:
        records = [OtlpMessage({"body": {"string_value": "test"}, "severityNumber": 9})]
        request = exporter._build_export_request(records)

        assert "resourceLogs" in request
        rl = request["resourceLogs"][0]
        assert "resource" in rl
        assert "scopeLogs" in rl
        sl = rl["scopeLogs"][0]
        assert sl["scope"]["name"] == "homeassistant"
        assert sl["scope"]["version"] == "1.0.0"
        assert sl["logRecords"] == [r.payload for r in records]

    async def test_flush_empty_buffer_is_noop(self, exporter: OtlpLogExporter) -> None:
        # Should not raise and not attempt any HTTP calls
        await exporter.flush()
        assert len(exporter._buffer) == 0

    def test_init_with_api_config(self, mock_entry_otel: MagicMock) -> None:
        mock_hass = MagicMock()
        mock_hass.config.api.local_ip = "192.168.1.100"
        mock_hass.config.api.port = 8123

        exporter = OtlpLogExporter(mock_hass, mock_entry_otel)

        assert exporter.server_address == "192.168.1.100"
        assert exporter.server_port == 8123
        attr_keys = [a["key"] for a in exporter._resource["attributes"]]
        assert "service.address" in attr_keys
        assert "service.port" in attr_keys

    def test_handle_event_triggers_flush_at_batch_size(self, exporter: OtlpLogExporter, mock_event: MagicMock) -> None:
        from unittest.mock import patch

        exporter._batch_max_size = 1
        with patch.object(exporter._hass, "async_create_task") as mock_create_task:
            exporter.handle_event(mock_event)
        mock_create_task.assert_called_once()

    def test_handle_event_exception_is_logged(self, exporter: OtlpLogExporter, mock_event: MagicMock) -> None:
        from unittest.mock import patch

        with patch.object(exporter, "_to_log_record", side_effect=RuntimeError("bad")):
            exporter.handle_event(mock_event)
        assert len(exporter._buffer) == 0

    async def test_flush_loop_cancelled(self, exporter: OtlpLogExporter) -> None:
        import asyncio
        from unittest.mock import patch

        with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await exporter.flush_loop()

    async def test_flush_sends_data_json(self, exporter: OtlpLogExporter, mock_event: MagicMock) -> None:
        from unittest.mock import AsyncMock, patch

        exporter.handle_event(mock_event)

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)

        with patch(
            "custom_components.remote_logger.otel.exporter.async_get_clientsession",
            return_value=mock_session,
        ):
            await exporter.flush()

        assert len(exporter._buffer) == 0
        mock_session.post.assert_called_once()

    async def test_flush_logs_on_http_error(self, exporter: OtlpLogExporter, mock_event: MagicMock) -> None:
        from unittest.mock import AsyncMock, patch

        exporter.handle_event(mock_event)

        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_resp.text = AsyncMock(return_value="server error")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)

        with patch(
            "custom_components.remote_logger.otel.exporter.async_get_clientsession",
            return_value=mock_session,
        ):
            await exporter.flush()
        # Should not raise

    async def test_flush_handles_client_error(self, exporter: OtlpLogExporter, mock_event: MagicMock) -> None:
        from unittest.mock import patch

        import aiohttp

        exporter.handle_event(mock_event)

        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=aiohttp.ClientError("conn failed"))

        with patch(
            "custom_components.remote_logger.otel.exporter.async_get_clientsession",
            return_value=mock_session,
        ):
            await exporter.flush()
        # Should not raise

    async def test_flush_protobuf(self, exporter_with_attrs: OtlpLogExporter, mock_event: MagicMock) -> None:
        from unittest.mock import AsyncMock, patch

        exporter_with_attrs.handle_event(mock_event)

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)

        with patch(
            "custom_components.remote_logger.otel.exporter.async_get_clientsession",
            return_value=mock_session,
        ):
            await exporter_with_attrs.flush()

        assert len(exporter_with_attrs._buffer) == 0

    async def test_close_is_noop(self, exporter: OtlpLogExporter) -> None:
        await exporter.close()  # Should not raise

    def test_to_log_record_event_data_as_attributes(self, exporter: OtlpLogExporter) -> None:
        data = {"domain": "light", "service": "turn_on", "count": 3}
        record = exporter._to_log_record(Event("homeassistant_start", data=data))
        attr_keys = [a["key"] for a in record.payload["attributes"]]
        assert "event.data.domain" in attr_keys
        assert "event.data.service" in attr_keys
        assert "event.data.count" in attr_keys

    def test_to_log_record_ha_event_name_as_event_name(self, exporter: OtlpLogExporter) -> None:
        record = exporter._to_log_record(Event("component_loaded"))
        assert record.payload["eventName"] == "component_loaded"

    def test_handle_ha_event_buffers(self, exporter: OtlpLogExporter) -> None:
        event = MagicMock()
        event.time_fired.timestamp.return_value = 1700000000.0
        event.data = {"domain": "light"}
        exporter.handle_ha_event("homeassistant_start", event)
        assert len(exporter._buffer) == 1
        assert exporter.event_count == 1

    def test_handle_ha_event_triggers_flush_at_batch_size(self, exporter: OtlpLogExporter) -> None:
        from unittest.mock import patch

        exporter._batch_max_size = 1
        event = MagicMock()
        event.time_fired.timestamp.return_value = 1700000000.0
        event.data = {}
        with patch.object(exporter._hass, "async_create_task") as mock_create_task:
            exporter.handle_ha_event("my_event", event)
        mock_create_task.assert_called_once()

    def test_handle_ha_event_exception_logged(self, exporter: OtlpLogExporter) -> None:
        from unittest.mock import patch

        event = MagicMock()
        event.time_fired.timestamp.return_value = 1700000000.0
        event.data = {}
        with patch.object(exporter, "_to_log_record", side_effect=RuntimeError("fail")):
            exporter.handle_ha_event("bad_event", event)
        assert exporter.format_error_count == 1

    def test_handle_ha_event_state_changed_message(self, exporter: OtlpLogExporter) -> None:
        from homeassistant.const import EVENT_STATE_CHANGED

        old_state = MagicMock()
        old_state.state = "off"
        new_state = MagicMock()
        new_state.state = "on"
        event = MagicMock()
        event.event_type = EVENT_STATE_CHANGED
        event.time_fired.timestamp.return_value = 1700000000.0
        event.data = {"entity_id": "light.kitchen", "old_state": old_state, "new_state": new_state}
        exporter.handle_ha_event(str(EVENT_STATE_CHANGED), event)
        body = exporter._buffer[0].payload["body"]["string_value"]
        assert "light.kitchen" in body
        assert "off" in body
        assert "on" in body
        assert "->" in body

    def test_handle_ha_event_state_changed_none_states(self, exporter: OtlpLogExporter) -> None:
        from homeassistant.const import EVENT_STATE_CHANGED

        event = MagicMock()
        event.event_type = EVENT_STATE_CHANGED
        event.time_fired.timestamp.return_value = 1700000000.0
        event.data = {"entity_id": "light.kitchen", "old_state": None, "new_state": None}
        exporter.handle_ha_event(str(EVENT_STATE_CHANGED), event)
        body = exporter._buffer[0].payload["body"]["string_value"]
        assert "N/A" in body

    def test_handle_ha_event_call_service_message(self, exporter: OtlpLogExporter) -> None:
        from homeassistant.core import EVENT_CALL_SERVICE

        event = MagicMock()
        event.event_type = EVENT_CALL_SERVICE
        event.time_fired.timestamp.return_value = 1700000000.0
        event.data = {"domain": "light", "service": "turn_on"}
        exporter.handle_ha_event(EVENT_CALL_SERVICE, event)
        body = exporter._buffer[0].payload["body"]["string_value"]
        assert "light" in body
        assert "turn_on" in body

    def test_handle_ha_event_component_loaded_message(self, exporter: OtlpLogExporter) -> None:
        from homeassistant.const import EVENT_COMPONENT_LOADED

        event = MagicMock()
        event.event_type = EVENT_COMPONENT_LOADED
        event.time_fired.timestamp.return_value = 1700000000.0
        event.data = {"component": "sensor"}
        exporter.handle_ha_event(EVENT_COMPONENT_LOADED, event)
        body = exporter._buffer[0].payload["body"]["string_value"]
        assert "sensor" in body

    def test_handle_ha_event_automation_triggered_message(self, exporter: OtlpLogExporter) -> None:
        from homeassistant.components.automation import EVENT_AUTOMATION_TRIGGERED

        event = MagicMock()
        event.event_type = EVENT_AUTOMATION_TRIGGERED
        event.time_fired.timestamp.return_value = 1700000000.0
        event.data = {"name": "My Automation", "entity_id": "automation.my_automation"}
        exporter.handle_ha_event(EVENT_AUTOMATION_TRIGGERED, event)
        body = exporter._buffer[0].payload["body"]["string_value"]
        assert "My Automation" in body
        assert "automation.my_automation" in body

    def test_handle_ha_event_user_added_message(self, exporter: OtlpLogExporter) -> None:
        from homeassistant.auth import EVENT_USER_ADDED

        event = MagicMock()
        event.event_type = EVENT_USER_ADDED
        event.time_fired.timestamp.return_value = 1700000000.0
        event.data = {"user_id": "abc123"}
        exporter.handle_ha_event(EVENT_USER_ADDED, event)
        body = exporter._buffer[0].payload["body"]["string_value"]
        assert "abc123" in body

    def test_handle_ha_event_general_fields_message(self, exporter: OtlpLogExporter) -> None:
        event = MagicMock()
        event.event_type = "custom_event"
        event.time_fired.timestamp.return_value = 1700000000.0
        event.data = {"name": "my thing", "device_id": "dev_42"}
        exporter.handle_ha_event("custom_event", event)
        body = exporter._buffer[0].payload["body"]["string_value"]
        assert "my thing" in body
        assert "dev_42" in body

    def test_handle_ha_event_default_message(self, exporter: OtlpLogExporter) -> None:
        event = MagicMock()
        event.event_type = "some_unknown_event"
        event.time_fired.timestamp.return_value = 1700000000.0
        event.data = {}
        exporter.handle_ha_event("some_unknown_event", event)
        body = exporter._buffer[0].payload["body"]["string_value"]
        assert body == "some_unknown_event"

    def test_handle_ha_event_body_serializes_event_data_as_json(self, exporter: OtlpLogExporter) -> None:
        import json

        event = MagicMock()
        event.event_type = "call_service"
        event.time_fired.timestamp.return_value = 1700000000.0
        event.data = {"domain": "light", "service": "turn_on", "entity_id": "light.x", "foo": 123}
        exporter.handle_ha_event("call_service", event, event_body=True)
        flat_event = exporter._buffer[0].payload["attributes"][3]["value"]["string_value"]
        parsed = json.loads(flat_event)
        assert parsed["foo"] == 123

    def test_handle_ha_event_body_restricts_attributes(self, exporter: OtlpLogExporter) -> None:
        event = MagicMock()
        event.event_type = "call_service"
        event.time_fired.timestamp.return_value = 1700000000.0
        event.data = {"domain": "light", "service": "turn_on", "entity_id": "light.x", "extra": "ignored"}
        exporter.handle_ha_event("call_service", event, event_body=True)
        attr_keys = [a["key"] for a in exporter._buffer[0].payload["attributes"]]
        assert "event.data.entity_id" in attr_keys
        assert "event.data.domain" in attr_keys
        assert "event.data.service" in attr_keys
        assert "event.data.extra" not in attr_keys

    def test_handle_ha_event_body_with_unserializable_object(self, exporter: OtlpLogExporter) -> None:
        import json

        class _Opaque:
            def __str__(self) -> str:
                return "custom_str"

        event = MagicMock()
        event.event_type = "custom_event"
        event.time_fired.timestamp.return_value = 1700000000.0
        event.data = {"key": _Opaque()}
        exporter.handle_ha_event("custom_event", event, event_body=True)
        flat_event = exporter._buffer[0].payload["attributes"][0]["value"]["string_value"]
        parsed = json.loads(flat_event)
        assert parsed["key"] == "custom_str"


class TestOtlpLogDirectMethod:
    @pytest.fixture
    def exporter(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> OtlpLogExporter:
        return OtlpLogExporter(hass, mock_entry_otel)

    def test_log_direct_buffers_record(self, exporter: OtlpLogExporter) -> None:
        exporter.log_direct("unit_test", "hello world", "INFO")
        assert len(exporter._buffer) == 1
        assert exporter.event_count == 1

    def test_log_direct_severity_levels(self, exporter: OtlpLogExporter) -> None:
        for level, (expected_num, expected_text) in {
            "DEBUG": (5, "DEBUG"),
            "INFO": (9, "INFO"),
            "WARNING": (13, "WARN"),
            "ERROR": (17, "ERROR"),
            "CRITICAL": (21, "FATAL"),
        }.items():
            exporter._buffer.clear()
            exporter.log_direct("unit_test", "msg", level)
            payload = exporter._buffer[0].payload
            assert payload["severityNumber"] == expected_num
            assert payload["severityText"] == expected_text

    def test_log_direct_message_in_body(self, exporter: OtlpLogExporter) -> None:
        exporter.log_direct("unit_test", "custom message", "INFO")
        assert exporter._buffer[0].payload["body"] == {"string_value": "custom message"}

    def test_log_direct_with_attributes(self, exporter: OtlpLogExporter) -> None:
        exporter.log_direct("unit_test", "msg", "INFO", {"env": "prod", "region": "eu"})
        attr_keys = [a["key"] for a in exporter._buffer[0].payload["attributes"]]
        assert "env" in attr_keys
        assert "region" in attr_keys

    def test_log_direct_no_attributes(self, exporter: OtlpLogExporter) -> None:
        exporter.log_direct("unit_test", "msg", "INFO")
        assert exporter._buffer[0].payload["attributes"] == []

    def test_log_direct_triggers_flush_at_batch_size(self, exporter: OtlpLogExporter) -> None:
        from unittest.mock import patch

        exporter._batch_max_size = 1
        with patch.object(exporter._hass, "async_create_task") as mock_create_task:
            exporter.log_direct("unit_test", "msg", "INFO")
        mock_create_task.assert_called_once()

    def test_log_direct_unknown_level_uses_default(self, exporter: OtlpLogExporter) -> None:
        exporter.log_direct("unit_test", "msg", "TRACE")
        payload = exporter._buffer[0].payload
        assert payload["severityNumber"] == 9
        assert payload["severityText"] == "INFO"


class TestOtelValidate:
    async def test_json_success(self) -> None:
        from unittest.mock import AsyncMock

        from custom_components.remote_logger.otel.exporter import validate

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)

        result = await validate(mock_session, "http://localhost:4318/v1/logs", "json")
        assert result == {}

    async def test_protobuf_success(self) -> None:
        from unittest.mock import AsyncMock

        from custom_components.remote_logger.otel.exporter import validate

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)

        result = await validate(mock_session, "http://localhost:4318/v1/logs", "protobuf")
        assert result == {}

    async def test_4xx_returns_cannot_connect(self) -> None:
        from unittest.mock import AsyncMock

        from custom_components.remote_logger.otel.exporter import validate

        mock_resp = MagicMock()
        mock_resp.status = 401
        mock_resp.text = AsyncMock(return_value="unauthorized")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)

        result = await validate(mock_session, "http://localhost:4318/v1/logs", "json")
        assert result == {"base": "cannot_connect"}

    async def test_5xx_returns_cannot_connect(self) -> None:
        from unittest.mock import AsyncMock

        from custom_components.remote_logger.otel.exporter import validate

        mock_resp = MagicMock()
        mock_resp.status = 503
        mock_resp.text = AsyncMock(return_value="service unavailable")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)

        result = await validate(mock_session, "http://localhost:4318/v1/logs", "json")
        assert result == {"base": "cannot_connect"}

    async def test_client_error(self) -> None:
        import aiohttp

        from custom_components.remote_logger.otel.exporter import validate

        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=aiohttp.ClientError("refused"))

        result = await validate(mock_session, "http://localhost:4318/v1/logs", "json")
        assert result == {"base": "cannot_connect"}

    async def test_unknown_error(self) -> None:
        from custom_components.remote_logger.otel.exporter import validate

        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=RuntimeError("unexpected"))

        result = await validate(mock_session, "http://localhost:4318/v1/logs", "json")
        assert result == {"base": "unknown"}

    async def test_unknown_encoding_raises(self) -> None:
        from custom_components.remote_logger.otel.exporter import validate

        mock_session = MagicMock()
        with pytest.raises(ValueError, match="Unknown encoding"):
            await validate(mock_session, "http://localhost/v1/logs", "xml")
