"""Unit tests for custom_components.remote_logger (setup/unload)."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING
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


class TestUpdateListener:
    async def test_update_listener_triggers_reload(self, hass: HomeAssistant, mock_entry_otel: MagicMock) -> None:
        from custom_components.remote_logger.remote_logger import _async_update_listener

        with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
            await _async_update_listener(hass, mock_entry_otel)

        mock_reload.assert_awaited_once_with(mock_entry_otel.entry_id)
