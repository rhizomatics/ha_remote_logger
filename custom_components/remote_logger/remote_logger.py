"""The remote_logger integration: ship HA system_log_event to an OTLP collector or syslog server."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from functools import partial
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.core import callback

from .const import (
    BACKEND_SYSLOG,
    CONF_BACKEND,
    CONF_CUSTOM_EVENTS,
    CONF_LOG_HA_CORE_ACTIVITY,
    CONF_LOG_HA_CORE_CHANGES,
    CONF_LOG_HA_EVENT_BODY,
    CONF_LOG_HA_FULL_STATE_CHANGES,
    CONF_LOG_HA_LIFECYCLE,
    CONF_LOG_HA_STATE_CHANGES,
    CORE_ACTIVITY_EVENTS,
    CORE_CHANGE_EVENTS,
    CORE_STATE_EVENTS,
    DOMAIN,
    EVENT_SYSTEM_LOG,
    LIFECYCLE_EVENTS,
    PLATFORMS,
)
from .otel.exporter import OtlpLogExporter
from .syslog.exporter import SyslogExporter

REF_CANCEL_LISTENERS = "cancel_listeners"
REF_FLUSH_TASK = "flush_task"
REF_EXPORTER = "exporter"

SERVICE_SEND_LOG = "send_log"
SERVICE_SEND_LOG_SCHEMA = vol.Schema({
    vol.Required("event"): str,
    vol.Required("message"): str,
    vol.Optional("level", default="INFO"): vol.In(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    vol.Optional("attributes"): dict,
})

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall

_LOGGER = logging.getLogger(__name__)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up remote logs from a config entry."""
    backend = entry.data.get(CONF_BACKEND)

    exporter: OtlpLogExporter | SyslogExporter
    if backend == BACKEND_SYSLOG:
        exporter = SyslogExporter(hass, entry)
        label: str = exporter.endpoint_desc
    else:
        exporter = OtlpLogExporter(hass, entry)
        label = exporter.endpoint_url

    # Options take precedence over initial data for the three event-subscription keys
    opts = {**entry.data, **entry.options}

    async def _flush_on_stop(_: Any) -> None:
        await exporter.flush()

    cancel_listeners: list[Callable[[], None]] = [
        hass.bus.async_listen(EVENT_SYSTEM_LOG, exporter.handle_event),
        hass.bus.async_listen_once("homeassistant_stop", _flush_on_stop),
        entry.add_update_listener(_async_update_listener),
    ]
    _LOGGER.info("remote_logger: listening for system_log_event, exporting %s to %s", backend, label)

    event_body: bool = bool(opts.get(CONF_LOG_HA_EVENT_BODY))

    if opts.get(CONF_LOG_HA_LIFECYCLE):
        cancel_listeners.extend(
            hass.bus.async_listen(et, partial(exporter.handle_ha_event, et, event_body=event_body)) for et in LIFECYCLE_EVENTS
        )
        _LOGGER.info("remote_logger: listening for HA lifecycle events")

    if opts.get(CONF_LOG_HA_CORE_CHANGES):
        cancel_listeners.extend(
            hass.bus.async_listen(et, partial(exporter.handle_ha_event, et, event_body=event_body)) for et in CORE_CHANGE_EVENTS
        )
        _LOGGER.info("remote_logger: listening for HA core config events")

    if opts.get(CONF_LOG_HA_STATE_CHANGES):
        cancel_listeners.extend(
            hass.bus.async_listen(et, partial(exporter.handle_ha_event, et, state_only=True, event_body=event_body))
            for et in CORE_STATE_EVENTS
        )
        _LOGGER.info("remote_logger: listening for HA state changes")

    if opts.get(CONF_LOG_HA_FULL_STATE_CHANGES):
        cancel_listeners.extend(
            hass.bus.async_listen(et, partial(exporter.handle_ha_event, et, state_only=False, event_body=event_body))
            for et in CORE_STATE_EVENTS
        )
        _LOGGER.info("remote_logger: listening for HA state changes")

    if opts.get(CONF_LOG_HA_CORE_ACTIVITY):
        cancel_listeners.extend(
            hass.bus.async_listen(et, partial(exporter.handle_ha_event, et, event_body=event_body))
            for et in CORE_ACTIVITY_EVENTS
        )
        _LOGGER.info("remote_logger: listening for HA core activity")

    custom_events_raw = opts.get(CONF_CUSTOM_EVENTS, "")
    cancel_listeners.extend(
        hass.bus.async_listen(et, partial(exporter.handle_ha_event, et, event_body=event_body))
        for et in (e.strip() for e in custom_events_raw.splitlines() if e.strip())
    )

    flush_task: asyncio.Task[None] = asyncio.create_task(exporter.flush_loop())

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        REF_CANCEL_LISTENERS: cancel_listeners,
        REF_FLUSH_TASK: flush_task,
        REF_EXPORTER: exporter,
    }

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_LOG):
        hass.services.async_register(
            DOMAIN, SERVICE_SEND_LOG, partial(handle_send_log, hass.data[DOMAIN]), schema=SERVICE_SEND_LOG_SCHEMA
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


@callback
def handle_send_log(domain_data: dict[str, Any], call: ServiceCall) -> None:
    message: str = call.data["message"]
    level: str = call.data["level"]
    event_name: str = call.data["event"]
    attributes: dict[str, Any] | None = call.data.get("attributes")
    for entry in domain_data.values():
        entry[REF_EXPORTER].log_direct(event_name, message, level, attributes)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload remote_logger config entry."""
    await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if data is None:
        return True

    for cancel in data.get(REF_CANCEL_LISTENERS, []):
        cancel()

    if data.get(REF_FLUSH_TASK):
        data[REF_FLUSH_TASK].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await data[REF_FLUSH_TASK]

    if data.get(REF_EXPORTER):
        await data[REF_EXPORTER].flush()
        await data[REF_EXPORTER].close()

    _LOGGER.info("remote_logger: unloaded, flushed remaining logs")
    return True
