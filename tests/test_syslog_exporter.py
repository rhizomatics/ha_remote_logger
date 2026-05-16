"""Unit tests for the syslog exporter."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from urllib.parse import urlparse

import pytest

from custom_components.remote_logger.syslog.exporter import (
    SyslogExporter,
    SyslogMessage,
    _sd_escape,
)

if TYPE_CHECKING:
    from homeassistant.core import Event, HomeAssistant

# ---------------------------------------------------------------------------
# _sd_escape
# ---------------------------------------------------------------------------


class TestSdEscape:
    def test_no_special_chars(self) -> None:
        assert _sd_escape("hello world") == "hello world"

    def test_escape_backslash(self) -> None:
        assert _sd_escape("path\\to") == "path\\\\to"

    def test_escape_double_quote(self) -> None:
        assert _sd_escape('say "hi"') == 'say \\"hi\\"'

    def test_escape_closing_bracket(self) -> None:
        assert _sd_escape("data]end") == "data\\]end"

    def test_escape_all_combined(self) -> None:
        assert _sd_escape('a\\b"c]d') == 'a\\\\b\\"c\\]d'


# ---------------------------------------------------------------------------
# SyslogExporter
# ---------------------------------------------------------------------------


class TestSyslogExporter:
    @pytest.fixture
    def exporter(self, hass: HomeAssistant, mock_entry_syslog: MagicMock) -> SyslogExporter:
        return SyslogExporter(hass, mock_entry_syslog)

    def test_init_properties(self, exporter: SyslogExporter) -> None:
        assert exporter._host == "syslog.example.com"
        assert exporter._port == 514
        assert exporter._protocol == "udp"
        assert exporter._app_name == "homeassistant"
        assert exporter._facility == 16  # local0
        assert exporter._hostname == "-"

    def test_name_from_entry_title(self, exporter: SyslogExporter) -> None:
        assert exporter.name == "Syslog Remote Logger"

    def test_endpoint_desc(self, exporter: SyslogExporter) -> None:
        url, protocol = exporter.endpoint_desc.split(" ")
        assert protocol == "(UDP)"
        parsed = urlparse(url)
        assert parsed.scheme == "syslog"
        assert parsed.hostname == "syslog.example.com"
        assert parsed.port == 514

    def test_endpoint_desc_tcp_tls(self, hass: HomeAssistant) -> None:
        entry = MagicMock()
        entry.data = {
            "host": "secure.example.com",
            "port": 6514,
            "protocol": "tcp",
            "use_tls": True,
            "app_name": "ha",
            "facility": "local0",
        }
        exp = SyslogExporter(hass, entry)
        assert "+TLS" in exp.endpoint_desc

    def test_to_syslog_message_format(self, exporter: SyslogExporter) -> None:
        data = {
            "name": "homeassistant.components.sensor",
            "message": ["Something went wrong"],
            "level": "ERROR",
            "timestamp": 1700000000.0,
            "exception": "Traceback (most recent call last):\n  File ...\nValueError: bad value",
            "count": 3,
            "first_occurred": 1699999000.0,
        }
        msg = exporter.create_log_record(data, "system_log_event", None)
        text = msg.payload.decode("utf-8")

        # Check RFC 5424 structure: <PRI>1 TIMESTAMP HOSTNAME APP-NAME - - SD MSG
        # PRI = facility(16) * 8 + severity(3 for ERROR) = 131
        assert text.startswith("<131>1 ")
        assert "homeassistant" in text
        assert "Something went wrong" in text

    def test_to_syslog_message_pri_calculation(self, exporter: SyslogExporter) -> None:
        # facility=16 (local0), severity=7 (DEBUG) -> PRI = 16*8 + 7 = 135
        data = {"level": "DEBUG", "message": ["debug msg"], "timestamp": 1700000000.0}
        msg = exporter.create_log_record(data, "system_log_event", None).payload.decode("utf-8")
        assert msg.startswith("<135>1 ")

    def test_to_syslog_message_warning_severity(self, exporter: SyslogExporter) -> None:
        # facility=16, severity=4 (WARNING) -> PRI = 132
        data = {"level": "WARNING", "message": ["warn"], "timestamp": 1700000000.0}
        msg = exporter.create_log_record(data, "system_log_event", None).payload.decode("utf-8")
        assert msg.startswith("<132>1 ")

    def test_to_syslog_message_critical_severity(self, exporter: SyslogExporter) -> None:
        # facility=16, severity=2 (CRITICAL) -> PRI = 130
        data = {"level": "CRITICAL", "message": ["crit"], "timestamp": 1700000000.0}
        msg = exporter.create_log_record(data, "system_log_event", None).payload.decode("utf-8")
        assert msg.startswith("<130>1 ")

    def test_to_syslog_message_default_severity(self, exporter: SyslogExporter) -> None:
        # Unknown level falls back to 6 (INFO) -> PRI = 134
        data = {"level": "TRACE", "message": ["trace"], "timestamp": 1700000000.0}
        msg = exporter.create_log_record(data, "system_log_event", None).payload.decode("utf-8")
        assert msg.startswith("<134>1 ")

    def test_to_syslog_message_includes_timestamp(self, exporter: SyslogExporter) -> None:
        data = {"message": ["test"], "timestamp": 1700000000.0}
        msg = exporter.create_log_record(data, "system_log_event", None).payload.decode("utf-8")
        # Should contain ISO 8601 timestamp
        assert "2023-11-14T" in msg

    def test_to_syslog_message_structured_data_with_logger(self, exporter: SyslogExporter) -> None:
        data = {
            "name": "my.logger",
            "message": ["test"],
            "level": "INFO",
            "timestamp": 1700000000.0,
            "count": 5,
            "first_occurred": 1699999000.0,
        }
        msg = exporter.create_log_record(data, "system_log_event", None).payload.decode("utf-8")
        assert '[opentelemetry code.function.name="my.logger"' in msg
        assert 'exception.count="5"' in msg
        assert 'exception.first_occurred="2023-11-14T13:56:40-08:00"' in msg

    def test_to_syslog_message_no_message(self, exporter: SyslogExporter) -> None:
        data = {"level": "INFO", "timestamp": 1700000000.0}
        msg = exporter.create_log_record(data, "system_log_event", None).payload.decode("utf-8")
        # Empty message list -> "-"
        # The msg field should be just "-" before any exception
        assert "- -" in msg  # PROCID=- MSGID=-

    def test_to_syslog_message_with_exception(self, exporter: SyslogExporter) -> None:
        data = {
            "message": ["error happened"],
            "level": "ERROR",
            "timestamp": 1700000000.0,
            "exception": "ValueError: bad",
        }
        msg = exporter.create_log_record(data, "system_log_event", None).payload.decode("utf-8")
        assert "error happened" in msg
        assert "ValueError: bad" in msg

    def test_to_syslog_message_empty_messages(self, exporter: SyslogExporter) -> None:
        data = {"message": [], "level": "INFO", "timestamp": 1700000000.0}
        msg = exporter.create_log_record(data, "system_log_event", None).payload.decode("utf-8")
        # empty message list -> "-"
        assert " - -" in msg or msg.endswith(" -")

    def test_handle_event_buffers(self, exporter: SyslogExporter, mock_event: MagicMock) -> None:
        assert len(exporter._buffer) == 0
        exporter.handle_event(mock_event)
        assert len(exporter._buffer) == 1

    def test_handle_event_prevents_syslog_loop(self, exporter: SyslogExporter) -> None:
        event = MagicMock()
        event.data = {
            "message": ["syslog error"],
            "level": "ERROR",
            "source": ("custom_components/remote_logger/syslog/exporter.py", 100),
        }
        exporter.handle_event(event)
        assert len(exporter._buffer) == 0

    def test_handle_event_allows_non_syslog_source(self, exporter: SyslogExporter) -> None:
        event = MagicMock()
        event.data = {
            "message": ["some error"],
            "level": "ERROR",
            "source": ("homeassistant/core.py", 50),
        }
        exporter.handle_event(event)
        assert len(exporter._buffer) == 1

    def test_different_facility(self, hass: HomeAssistant) -> None:
        entry = MagicMock()
        entry.data = {
            "host": "localhost",
            "port": 514,
            "protocol": "udp",
            "use_tls": False,
            "app_name": "ha",
            "facility": "daemon",
        }
        exp = SyslogExporter(hass, entry)
        assert exp._facility == 3  # daemon facility code

    async def test_flush_empty_buffer_is_noop(self, exporter: SyslogExporter) -> None:
        await exporter.flush()
        assert len(exporter._buffer) == 0

    def test_to_protobuf(self, exporter: SyslogExporter, sample_log_event: Event) -> None:
        msg = exporter.create_log_record(
            sample_log_event.data, sample_log_event.event_type, sample_log_event.time_fired
        ).payload.decode("utf-8")
        assert msg is not None
        assert msg.startswith("<131>")
        assert len(msg) > 300

    def test_handle_event_triggers_flush_at_batch_size(self, exporter: SyslogExporter, mock_event: MagicMock) -> None:
        from unittest.mock import patch

        exporter._batch_max_size = 1
        with patch.object(exporter._hass, "async_create_task") as mock_create_task:
            exporter.handle_event(mock_event)
        mock_create_task.assert_called_once()

    async def test_flush_loop_cancelled(self, exporter: SyslogExporter) -> None:
        import asyncio
        from unittest.mock import patch

        with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await exporter.flush_loop()

    async def test_flush_sends_via_udp(self, exporter: SyslogExporter, mock_event: MagicMock) -> None:
        from unittest.mock import AsyncMock, patch

        exporter.handle_event(mock_event)

        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_loop = MagicMock()
        mock_loop.create_datagram_endpoint = AsyncMock(return_value=(mock_transport, None))

        with patch("asyncio.get_running_loop", return_value=mock_loop):
            await exporter.flush()

        assert len(exporter._buffer) == 0
        mock_transport.sendto.assert_called_once()

    async def test_flush_sends_via_tcp(self, hass: HomeAssistant, mock_event: MagicMock) -> None:
        from unittest.mock import AsyncMock, patch

        entry = MagicMock()
        entry.data = {
            "host": "syslog.example.com",
            "port": 514,
            "protocol": "tcp",
            "use_tls": False,
            "app_name": "homeassistant",
            "facility": "local0",
        }
        exporter = SyslogExporter(hass, entry)
        exporter.handle_event(mock_event)

        mock_writer = AsyncMock()
        mock_writer.is_closing.return_value = False

        async def fake_connect() -> None:
            exporter._tcp_writer = mock_writer

        with patch.object(exporter, "_connect_tcp", side_effect=fake_connect):
            await exporter.flush()

        assert len(exporter._buffer) == 0
        mock_writer.drain.assert_awaited_once()

    async def test_send_udp_creates_transport(self, exporter: SyslogExporter) -> None:
        from unittest.mock import AsyncMock, patch

        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_loop = MagicMock()
        mock_loop.create_datagram_endpoint = AsyncMock(return_value=(mock_transport, None))

        with patch("asyncio.get_running_loop", return_value=mock_loop):
            await exporter._send_udp([SyslogMessage(b"hello"), SyslogMessage(b"world")])

        assert exporter._udp_transport is mock_transport
        assert mock_transport.sendto.call_count == 2

    async def test_send_udp_reuses_existing_transport(self, exporter: SyslogExporter) -> None:
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        exporter._udp_transport = mock_transport

        await exporter._send_udp([SyslogMessage(b"msg")])

        mock_transport.sendto.assert_called_once_with(b"msg")

    async def test_send_udp_os_error_clears_transport(self, exporter: SyslogExporter) -> None:
        from unittest.mock import AsyncMock, patch

        mock_loop = MagicMock()
        mock_loop.create_datagram_endpoint = AsyncMock(side_effect=OSError("refused"))

        with patch("asyncio.get_running_loop", return_value=mock_loop):
            await exporter._send_udp([SyslogMessage(b"msg")])

        assert exporter._udp_transport is None

    async def test_send_tcp_with_existing_writer(self, exporter: SyslogExporter) -> None:
        from unittest.mock import AsyncMock

        # Use MagicMock for is_closing (sync) and AsyncMock only for drain (async)
        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = False
        mock_writer.drain = AsyncMock()
        exporter._tcp_writer = mock_writer

        await exporter._send_tcp([SyslogMessage(b"test")])

        mock_writer.write.assert_called_once()
        mock_writer.drain.assert_awaited_once()

    async def test_send_tcp_os_error_closes(self, exporter: SyslogExporter) -> None:
        from unittest.mock import AsyncMock

        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = False
        mock_writer.drain = AsyncMock(side_effect=OSError("broken pipe"))
        exporter._tcp_writer = mock_writer

        await exporter._send_tcp([SyslogMessage(b"test")])
        # Should have called _close_tcp
        assert exporter._tcp_writer is None

    async def test_connect_tcp_no_tls(self, exporter: SyslogExporter) -> None:
        from unittest.mock import AsyncMock, patch

        mock_reader = MagicMock()
        mock_writer = MagicMock()

        with patch("asyncio.wait_for", new=AsyncMock(return_value=(mock_reader, mock_writer))):
            await exporter._connect_tcp()

        assert exporter._tcp_reader is mock_reader
        assert exporter._tcp_writer is mock_writer

    async def test_connect_tcp_with_tls(self, hass: HomeAssistant) -> None:
        import ssl
        from unittest.mock import AsyncMock, patch

        entry = MagicMock()
        entry.data = {
            "host": "secure.host",
            "port": 6514,
            "protocol": "tcp",
            "use_tls": True,
            "app_name": "ha",
            "facility": "local0",
        }
        exporter = SyslogExporter(hass, entry)

        mock_reader = MagicMock()
        mock_writer = MagicMock()

        with patch("asyncio.wait_for", new=AsyncMock(return_value=(mock_reader, mock_writer))):
            with patch("ssl.create_default_context", return_value=MagicMock(spec=ssl.SSLContext)):
                await exporter._connect_tcp()

        assert exporter._tcp_writer is mock_writer

    async def test_close_tcp_with_writer(self, exporter: SyslogExporter) -> None:
        from unittest.mock import AsyncMock

        mock_writer = AsyncMock()
        exporter._tcp_writer = mock_writer
        exporter._tcp_reader = MagicMock()

        await exporter._close_tcp()

        mock_writer.close.assert_called_once()
        assert exporter._tcp_writer is None
        assert exporter._tcp_reader is None

    async def test_close_all_resources(self, exporter: SyslogExporter) -> None:
        from unittest.mock import AsyncMock

        mock_udp = MagicMock()
        mock_writer = AsyncMock()
        exporter._udp_transport = mock_udp
        exporter._tcp_writer = mock_writer

        await exporter.close()

        mock_udp.close.assert_called_once()
        assert exporter._udp_transport is None
        assert exporter._tcp_writer is None

    def test_to_syslog_message_event_data_in_sd(self, exporter: SyslogExporter) -> None:
        data = {
            "domain": "light",
            "service": "turn_on",
        }
        msg = exporter.create_log_record(data, "service_registered", None).payload.decode("utf-8")
        assert 'event.data.domain="light"' in msg
        assert 'event.data.service="turn_on"' in msg

    def test_to_syslog_message_msgid_from_event(self, exporter: SyslogExporter) -> None:
        msg = exporter.create_log_record({}, "component_loaded", None).payload.decode("utf-8")
        # MSGID field (6th SP-delimited token) should be the event type
        parts = msg.split(" ")
        assert parts[5] == "component_loaded"

    def test_to_syslog_message_msgid_default_for_system_log(self, exporter: SyslogExporter) -> None:
        data = {"level": "ERROR", "message": ["err"], "timestamp": 1700000000.0}
        msg = exporter.create_log_record(data, "system_log_event", None).payload.decode("utf-8")
        parts = msg.split(" ")
        assert parts[5] == "-"

    def test_handle_ha_event_buffers(self, exporter: SyslogExporter) -> None:
        event = MagicMock()
        event.time_fired.timestamp.return_value = 1700000000.0
        event.data = {"domain": "light"}
        exporter.handle_ha_event("homeassistant_stop", event)
        assert len(exporter._buffer) == 1
        assert exporter.event_count == 1


class TestSyslogLogDirectMethod:
    @pytest.fixture
    def exporter(self, hass: HomeAssistant, mock_entry_syslog: MagicMock) -> SyslogExporter:
        return SyslogExporter(hass, mock_entry_syslog)

    def test_log_direct_buffers_record(self, exporter: SyslogExporter) -> None:
        exporter.log_direct("unit_test", "hello syslog", "INFO")
        assert len(exporter._buffer) == 1
        assert exporter.event_count == 1

    def test_log_direct_message_in_payload(self, exporter: SyslogExporter) -> None:
        exporter.log_direct("unit_test", "my message", "INFO")
        payload = exporter._buffer[0].payload.decode()
        assert "my message" in payload

    def test_log_direct_rfc5424_format(self, exporter: SyslogExporter) -> None:
        exporter.log_direct("unit_test", "test", "ERROR")
        payload = exporter._buffer[0].payload.decode()
        # <PRI>1 TIMESTAMP HOSTNAME APP-NAME PROCID MSGID SD MSG
        assert payload.startswith("<")
        assert ">1 " in payload
        assert "homeassistant" in payload

    def test_log_direct_with_attributes(self, exporter: SyslogExporter) -> None:
        exporter.log_direct("unit_test", "msg", "INFO", {"env": "prod"})
        payload = exporter._buffer[0].payload.decode()
        assert 'env="prod"' in payload

    def test_log_direct_no_attributes_uses_nil_sd(self, exporter: SyslogExporter) -> None:
        exporter.log_direct("unit_test", "msg", "WARNING")
        payload = exporter._buffer[0].payload.decode()
        assert " - " in payload  # nil SD field

    def test_log_direct_triggers_flush_at_batch_size(self, exporter: SyslogExporter) -> None:
        from unittest.mock import patch

        exporter._batch_max_size = 1
        with patch.object(exporter._hass, "async_create_task") as mock_create_task:
            exporter.log_direct("unit_test", "msg", "INFO")
        mock_create_task.assert_called_once()


class TestSyslogValidate:
    async def test_udp_success(self, hass: HomeAssistant) -> None:
        from unittest.mock import patch

        from custom_components.remote_logger.syslog.exporter import validate

        with patch("socket.socket"):
            with patch("socket.getaddrinfo", return_value=[("AF_INET", "SOCK_DGRAM", 0, "", ("127.0.0.1", 514))]):
                result = await validate(hass, "localhost", 514, "udp", False)

        assert result is None

    async def test_tcp_success(self, hass: HomeAssistant) -> None:
        from unittest.mock import AsyncMock, patch

        from custom_components.remote_logger.syslog.exporter import validate

        mock_writer = AsyncMock()
        with patch("asyncio.wait_for", new=AsyncMock(return_value=(MagicMock(), mock_writer))):
            result = await validate(hass, "localhost", 514, "tcp", False)

        assert result is None
        mock_writer.close.assert_called_once()

    async def test_tcp_connection_refused(self, hass: HomeAssistant) -> None:
        from unittest.mock import AsyncMock, patch

        from custom_components.remote_logger.syslog.exporter import validate

        with patch("asyncio.wait_for", new=AsyncMock(side_effect=ConnectionRefusedError)):
            result = await validate(hass, "localhost", 514, "tcp", False)

        assert result == "cannot_connect"

    async def test_udp_os_error(self, hass: HomeAssistant) -> None:
        from unittest.mock import patch

        from custom_components.remote_logger.syslog.exporter import validate

        with patch("socket.socket", side_effect=OSError("network unreachable")):
            result = await validate(hass, "localhost", 514, "udp", False)

        assert result == "cannot_connect"

    async def test_unknown_error(self, hass: HomeAssistant) -> None:
        from unittest.mock import patch

        from custom_components.remote_logger.syslog.exporter import validate

        with patch("socket.socket", side_effect=RuntimeError("unexpected")):
            result = await validate(hass, "localhost", 514, "udp", False)

        assert result == "unknown"
