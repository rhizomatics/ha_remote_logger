"""Unit tests for custom_components.remote_logger (setup/unload)."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.remote_logger import async_setup_entry, async_unload_entry
from custom_components.remote_logger.const import (
    CONF_CUSTOM_EVENTS,
    CONF_LOG_HA_CORE_CHANGES,
    CONF_LOG_HA_LIFECYCLE,
    CORE_CHANGE_EVENTS,
    DOMAIN,
    LIFECYCLE_EVENTS,
)
from custom_components.remote_logger.otel.exporter import OtlpJsonSubmission, OtlpMessage

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


class TestAsyncSetupEntry:
    async def test_otel_backend(self, hass: HomeAssistant, mock_entry_otel: ConfigEntry) -> None:
        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            result = await async_setup_entry(hass, mock_entry_otel)

        assert result is True
        assert mock_entry_otel.entry_id in hass.data[DOMAIN]
        entry_data = hass.data[DOMAIN][mock_entry_otel.entry_id]
        assert "flush_task" in entry_data
        assert "exporter" in entry_data

        # Cancel the background flush task
        entry_data["flush_task"].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await entry_data["flush_task"]

    async def test_syslog_backend(self, hass: HomeAssistant, mock_entry_syslog: ConfigEntry) -> None:
        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            result = await async_setup_entry(hass, mock_entry_syslog)

        assert result is True
        assert mock_entry_syslog.entry_id in hass.data[DOMAIN]

        # Cancel the background flush task
        entry_data = hass.data[DOMAIN][mock_entry_syslog.entry_id]
        entry_data["flush_task"].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await entry_data["flush_task"]

    async def test_lifecycle_events_registered(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:
        mock_entry_otel.data = {**mock_entry_otel.data, CONF_LOG_HA_LIFECYCLE: True}
        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_otel)

        entry_data = hass.data[DOMAIN][mock_entry_otel.entry_id]
        # system_log + update_listener + 3 lifecycle listeners
        assert len(entry_data["cancel_listeners"]) == 5 + len(LIFECYCLE_EVENTS)

        entry_data["flush_task"].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await entry_data["flush_task"]

    async def test_core_change_events_registered(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:
        mock_entry_otel.data = {**mock_entry_otel.data, CONF_LOG_HA_CORE_CHANGES: True}
        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_otel)

        entry_data = hass.data[DOMAIN][mock_entry_otel.entry_id]
        assert len(entry_data["cancel_listeners"]) == 5 + len(CORE_CHANGE_EVENTS)

        entry_data["flush_task"].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await entry_data["flush_task"]

    async def test_custom_events_registered(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:
        mock_entry_otel.data = {**mock_entry_otel.data, CONF_CUSTOM_EVENTS: "my_event\nanother_event\n"}
        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_otel)

        entry_data = hass.data[DOMAIN][mock_entry_otel.entry_id]
        assert (
            len(entry_data["cancel_listeners"]) == 5 + 2
        )  # system_log + stop_listener + final_write + shutdown + update_listener + 2 custom

        entry_data["flush_task"].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await entry_data["flush_task"]

    async def test_options_override_data(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:
        """Options take precedence over data for event config keys."""
        mock_entry_otel.data = {**mock_entry_otel.data, CONF_LOG_HA_LIFECYCLE: False}
        mock_entry_otel.options = {CONF_LOG_HA_LIFECYCLE: True}
        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_otel)

        entry_data = hass.data[DOMAIN][mock_entry_otel.entry_id]
        assert len(entry_data["cancel_listeners"]) == 5 + len(LIFECYCLE_EVENTS)

        entry_data["flush_task"].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await entry_data["flush_task"]


class TestAsyncUnloadEntry:
    async def _setup_entry_data(self, hass: HomeAssistant, entry_id: str) -> tuple[MagicMock, asyncio.Task[None], AsyncMock]:
        cancel_listener = MagicMock()

        mock_exporter = AsyncMock()

        async def _long_sleep() -> None:
            await asyncio.sleep(1000)

        flush_task: asyncio.Task[None] = asyncio.create_task(_long_sleep())
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry_id] = {
            "cancel_listeners": [cancel_listener],
            "flush_task": flush_task,
            "exporter": mock_exporter,
        }
        return cancel_listener, flush_task, mock_exporter

    async def test_unload_cancels_task_and_flushes(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:
        cancel_listener, flush_task, mock_exporter = await self._setup_entry_data(hass, mock_entry_otel.entry_id)

        with patch.object(hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)):
            result = await async_unload_entry(hass, mock_entry_otel)

        assert result is True
        assert flush_task.cancelled()
        cancel_listener.assert_called_once()
        mock_exporter.flush.assert_awaited_once()
        mock_exporter.close.assert_awaited_once()
        assert mock_entry_otel.entry_id not in hass.data[DOMAIN]

    async def test_unload_missing_entry_returns_true(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:
        hass.data[DOMAIN] = {}
        with patch.object(hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)):
            result = await async_unload_entry(hass, mock_entry_otel)
        assert result is True


class TestShutdownFlush:
    async def test_homeassistant_stop_flushes_exporter(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:
        from unittest.mock import AsyncMock, patch

        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_otel)

        entry_data = hass.data[DOMAIN][mock_entry_otel.entry_id]
        exporter = entry_data["exporter"]

        with patch.object(exporter, "flush", AsyncMock()) as mock_flush:
            hass.bus.async_fire("homeassistant_stop")
            await hass.async_block_till_done()

        mock_flush.assert_awaited_once()

        entry_data["flush_task"].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await entry_data["flush_task"]


class TestSendLogService:
    async def test_service_registered_on_otel_setup(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:
        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_otel)

        entry_data = hass.data[DOMAIN][mock_entry_otel.entry_id]
        entry_data["flush_task"].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await entry_data["flush_task"]

        assert hass.services.has_service("remote_logger", "send_log")

    async def test_service_registered_on_syslog_setup(self, hass: HomeAssistant, mock_entry_syslog: MagicMock) -> None:
        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_syslog)

        entry_data = hass.data[DOMAIN][mock_entry_syslog.entry_id]
        entry_data["flush_task"].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await entry_data["flush_task"]

        assert hass.services.has_service("remote_logger", "send_log")

    async def test_send_log_routes_to_otel_exporter(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:
        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_otel)

        entry_data = hass.data[DOMAIN][mock_entry_otel.entry_id]
        exporter = entry_data["exporter"]

        await hass.services.async_call(
            "remote_logger", "send_log", {"event": "unit_test", "message": "direct log", "level": "ERROR"}, blocking=True
        )

        assert len(exporter._buffer) == 1
        assert exporter._buffer[0].payload["body"] == {"stringValue": "direct log"}
        assert exporter._buffer[0].payload["severityNumber"] == 17

        entry_data["flush_task"].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await entry_data["flush_task"]

    async def test_send_log_routes_to_syslog_exporter(self, hass: HomeAssistant, mock_entry_syslog: MagicMock) -> None:
        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_syslog)

        entry_data = hass.data[DOMAIN][mock_entry_syslog.entry_id]
        exporter = entry_data["exporter"]

        await hass.services.async_call(
            "remote_logger", "send_log", {"event": "unit_test", "message": "syslog direct"}, blocking=True
        )

        assert len(exporter._buffer) == 1
        assert b"syslog direct" in exporter._buffer[0].payload

        entry_data["flush_task"].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await entry_data["flush_task"]

    async def test_send_log_not_registered_twice(
        self, hass: HomeAssistant, mock_entry_otel: MagicMock, mock_entry_syslog: MagicMock
    ) -> None:
        """Service is registered once even when multiple entries are set up."""
        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_otel)
            await async_setup_entry(hass, mock_entry_syslog)

        assert hass.services.has_service("remote_logger", "send_log")

        for entry_id in [mock_entry_otel.entry_id, mock_entry_syslog.entry_id]:
            hass.data[DOMAIN][entry_id]["flush_task"].cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hass.data[DOMAIN][entry_id]["flush_task"]


class TestFlushService:
    async def test_flush_service_registered(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:
        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_otel)

        entry_data = hass.data[DOMAIN][mock_entry_otel.entry_id]
        entry_data["flush_task"].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await entry_data["flush_task"]

        assert hass.services.has_service("remote_logger", "flush")

    async def test_flush_service_calls_exporter_flush(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:
        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_otel)

        entry_data = hass.data[DOMAIN][mock_entry_otel.entry_id]
        exporter = entry_data["exporter"]

        with patch.object(exporter, "flush", AsyncMock()) as mock_flush:
            await hass.services.async_call("remote_logger", "flush", blocking=True)

        mock_flush.assert_awaited_once()

        entry_data["flush_task"].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await entry_data["flush_task"]

    async def test_flush_not_registered_twice(
        self, hass: HomeAssistant, mock_entry_otel: MagicMock, mock_entry_syslog: MagicMock
    ) -> None:
        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_otel)
            await async_setup_entry(hass, mock_entry_syslog)

        assert hass.services.has_service("remote_logger", "flush")

        for entry_id in [mock_entry_otel.entry_id, mock_entry_syslog.entry_id]:
            hass.data[DOMAIN][entry_id]["flush_task"].cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hass.data[DOMAIN][entry_id]["flush_task"]


class TestLastLogService:
    async def test_last_log_service_registered(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:
        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_otel)

        assert hass.services.has_service("remote_logger", "last_log")

    async def test_last_log_returns_empty_before_any_send(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:
        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_otel)

        result = await hass.services.async_call(
            "remote_logger", "last_log", {"config_entry_id": mock_entry_otel.entry_id}, blocking=True, return_response=True
        )

        assert result == {}

    async def test_last_log_returns_payload_after_send(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:
        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_otel)

        entry_data = hass.data[DOMAIN][mock_entry_otel.entry_id]
        exporter = entry_data["exporter"]
        exporter.last_sent_payload = OtlpJsonSubmission(
            {}, records=[OtlpMessage(payload={"body": {"stringValue": "hello"}, "severityText": "INFO"})]
        )

        result = await hass.services.async_call(
            "remote_logger", "last_log", {"config_entry_id": mock_entry_otel.entry_id}, blocking=True, return_response=True
        )

        assert result == {
            "headers": {"Content-Type": "application/json"},
            "json": {
                "resourceLogs": [
                    {
                        "resource": {},
                        "scopeLogs": [
                            {
                                "scope": {"name": "homeassistant", "version": "1.0.0"},
                                "logRecords": [{"body": {"stringValue": "hello"}, "severityText": "INFO"}],
                            }
                        ],
                    }
                ]
            },
        }

    async def test_last_log_otel_json_after_flush(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:
        from unittest.mock import AsyncMock as _AsyncMock
        from unittest.mock import patch as _patch

        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_otel)

        exporter = hass.data[DOMAIN][mock_entry_otel.entry_id]["exporter"]
        exporter.log_direct("test.event", "hello json", "INFO")

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status = 200
        mock_resp.__aenter__ = _AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = _AsyncMock(return_value=False)

        with _patch("aiohttp.ClientSession.post", return_value=mock_resp):
            await exporter.flush()

        result = await hass.services.async_call(
            "remote_logger", "last_log", {"config_entry_id": mock_entry_otel.entry_id}, blocking=True, return_response=True
        )

        assert result["headers"]["Content-Type"] == "application/json"
        log_record = result["json"]["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]
        assert log_record["body"]["stringValue"] == "hello json"

    async def test_last_log_otel_protobuf_after_flush(self, hass: HomeAssistant, mock_entry_otel_protobuf: MagicMock) -> None:
        from unittest.mock import AsyncMock as _AsyncMock
        from unittest.mock import patch as _patch

        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_otel_protobuf)

        exporter = hass.data[DOMAIN][mock_entry_otel_protobuf.entry_id]["exporter"]
        exporter.log_direct("test.event", "hello protobuf", "WARNING")

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status = 200
        mock_resp.__aenter__ = _AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = _AsyncMock(return_value=False)

        with _patch("aiohttp.ClientSession.post", return_value=mock_resp):
            await exporter.flush()

        result = await hass.services.async_call(
            "remote_logger",
            "last_log",
            {"config_entry_id": mock_entry_otel_protobuf.entry_id},
            blocking=True,
            return_response=True,
        )

        assert result["headers"]["Content-Type"] == "application/x-protobuf"
        assert isinstance(result["data"], str)
        assert "hello protobuf" in result["data"]
        assert "\ufffd" not in result["data"]

    async def test_last_log_syslog_after_flush(self, hass: HomeAssistant, mock_entry_syslog: MagicMock) -> None:
        from unittest.mock import AsyncMock as _AsyncMock
        from unittest.mock import patch as _patch

        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_syslog)

        exporter = hass.data[DOMAIN][mock_entry_syslog.entry_id]["exporter"]
        exporter.log_direct("test.event", "hello syslog", "ERROR")

        with _patch.object(exporter, "_send_udp", _AsyncMock()) as mock_send:
            mock_send.side_effect = lambda msgs: [setattr(m, "sent", True) for m in msgs]  # type:ignore[func-returns-value]
            await exporter.flush()

        result = await hass.services.async_call(
            "remote_logger", "last_log", {"config_entry_id": mock_entry_syslog.entry_id}, blocking=True, return_response=True
        )

        assert result["protocol"] == "udp"
        assert "hello syslog" in result["data"]

    async def test_last_log_returns_empty_dict_for_unknown_entry(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:

        with patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()):
            await async_setup_entry(hass, mock_entry_otel)

        result: dict[str, Any] = await hass.services.async_call(
            "remote_logger", "last_log", {"config_entry_id": "nonexistent"}, blocking=True, return_response=True
        )
        assert result == {}


class TestUpdateListener:
    async def test_update_listener_triggers_reload(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:
        from custom_components.remote_logger.remote_logger import _async_update_listener

        with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
            await _async_update_listener(hass, mock_entry_otel)

        mock_reload.assert_awaited_once_with(mock_entry_otel.entry_id)
