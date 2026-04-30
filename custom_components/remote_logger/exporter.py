import asyncio
import json
import logging
import threading
from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.auth import EVENT_USER_ADDED, EVENT_USER_REMOVED, EVENT_USER_UPDATED, HomeAssistant
from homeassistant.components.automation import EVENT_AUTOMATION_TRIGGERED
from homeassistant.components.script import EVENT_SCRIPT_STARTED
from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_STATE_CHANGED
from homeassistant.core import EVENT_CALL_SERVICE, EVENT_SERVICE_REGISTERED, EVENT_SERVICE_REMOVED, Event, callback
from homeassistant.helpers.area_registry import EVENT_AREA_REGISTRY_UPDATED
from homeassistant.helpers.category_registry import EVENT_CATEGORY_REGISTRY_UPDATED
from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED
from homeassistant.helpers.floor_registry import EVENT_FLOOR_REGISTRY_UPDATED
from homeassistant.helpers.label_registry import EVENT_LABEL_REGISTRY_UPDATED
from homeassistant.util import dt as dt_util

from custom_components.remote_logger.const import BATCH_FLUSH_INTERVAL_SECONDS

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Mapping

_LOGGER = logging.getLogger(__name__)

_HA_EVENT_BODY_ATTRIBUTE_KEYS: frozenset[str] = frozenset({"entity_id", "domain", "service"})


def _event_data_serializer(obj: Any) -> Any:
    """JSON serializer for HA event data objects."""
    if hasattr(obj, "as_dict"):
        return obj.as_dict()
    if hasattr(obj, "value"):
        return obj.value
    return str(obj)


@dataclass
class LogMessage:
    payload: Any
    sent: bool = False


class LogSubmission:
    @abstractmethod
    def for_display(self) -> dict[str, Any]:
        pass


class LogExporter:
    """Base class for log exporters"""

    logger_type: str

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass: HomeAssistant = hass
        self.name: str = self.logger_type
        self.destination: tuple[str, ...]
        self.tz = dt_util.get_default_time_zone()

        self._batch_max_size: int
        self.event_count: int = 0
        self.last_event: dt.datetime | None = None
        self.posting_count: int = 0
        self.last_posting: dt.datetime | None = None
        self.format_error_count: int = 0
        self.last_format_error_message: str | None = None
        self.last_format_error: dt.datetime | None = None
        self.posting_error_count: int = 0
        self.last_posting_error_message: str | None = None
        self.last_posting_error: dt.datetime | None = None

        self._buffer: list[LogMessage] = []
        self.self_source: str = f"custom_components/remote_logger/{self.logger_type}"
        self.last_sent_payload: LogSubmission | None = None
        self.flushing: threading.Event = threading.Event()

    async def disable_buffer(self) -> None:
        """Flush logs and prevent future buffering, use for shutdowns"""
        self._batch_max_size = 0
        self.flushing.clear()
        await self.flush()

    @callback
    def handle_event(self, event: Event) -> None:
        self.on_event()
        if (
            event.data
            and event.data.get("source")
            and len(event.data["source"]) == 2
            and self.self_source in event.data["source"][0]
        ):
            # prevent log loops
            return
        try:
            record: LogMessage = self.event_to_log_record(event)
            self._buffer.append(record)

            if len(self._buffer) >= self._batch_max_size:
                self._hass.async_create_task(self.flush())
        except Exception as e:
            _LOGGER.error("remote_logger: %s event handler failure %s on %s", self.logger_type, e, event.data)
            self.on_format_error(str(e))

    def handle_entry(self, entry: Mapping[str, Any], time_fired: dt.datetime) -> None:
        self.on_event()
        if entry and entry.get("source") and len(entry["source"]) == 2 and self.self_source in entry["source"][0]:
            # prevent log loops
            return
        try:
            record: LogMessage = self.create_log_record(entry, None, time_fired)
            self._buffer.append(record)

            if len(self._buffer) >= self._batch_max_size:
                self._hass.create_task(self.flush())
        except Exception as e:
            _LOGGER.error("remote_logger: %s entry handler failure %s on %s", self.logger_type, e, entry)
            self.on_format_error(str(e))

    @abstractmethod
    def create_log_record(
        self,
        event_data: Mapping[str, Any],
        event_type: str | None = None,
        time_fired: dt.datetime | None = None,
        message_override: list[str] | None = None,
        level_override: str | None = None,
        state_only: bool = False,
    ) -> LogMessage:
        pass

    @callback
    def handle_ha_event(self, event_type: str, event: Event, state_only: bool = False, event_body: bool = False) -> None:
        """Handle a non-system-log HA event (lifecycle, core change, or custom)."""
        self.on_event()
        title_fields: list[str] = ["message", "id", "entity_id", "name", "component", "device_id"]
        try:
            if (
                event_type == EVENT_CALL_SERVICE
                and event.data.get("domain") == "system_log"
                and event.data.get("service") == "write"
            ):
                # don't double count log events
                return
            if event_type == EVENT_STATE_CHANGED:
                old_state: str = (event.data["old_state"] and event.data["old_state"].state) or "N/A"
                new_state: str = (event.data["new_state"] and event.data["new_state"].state) or "N/A"
                message: list[str] = [event_type, ":", event.data["entity_id"], old_state, "->", new_state]
            elif event_type in (EVENT_CALL_SERVICE, EVENT_SERVICE_REGISTERED, EVENT_SERVICE_REMOVED):
                message = [event_type, ":", event.data["domain"], event.data["service"]]
            elif event_type == EVENT_COMPONENT_LOADED:
                message = [event_type, ":", event.data["component"]]
            elif event_type in (EVENT_SCRIPT_STARTED, EVENT_AUTOMATION_TRIGGERED):
                message = [event_type, ":", event.data["entity_id"]]
            elif event_type == EVENT_DEVICE_REGISTRY_UPDATED:
                message = [event_type, ":", event.data["device_id"], event.data.get("action", "???")]
            elif event_type == EVENT_ENTITY_REGISTRY_UPDATED:
                message = [event_type, ":", event.data["entity_id"], event.data.get("action", "???")]
            elif event_type == EVENT_LABEL_REGISTRY_UPDATED:
                message = [event_type, ":", event.data["label_id"], event.data.get("action", "???")]
            elif event_type == EVENT_AREA_REGISTRY_UPDATED:
                message = [event_type, ":", event.data["area_id"], event.data.get("action", "???")]
            elif event_type == EVENT_CATEGORY_REGISTRY_UPDATED:
                message = [event_type, ":", event.data["category_id"], event.data.get("action", "???")]
            elif event_type == EVENT_FLOOR_REGISTRY_UPDATED:
                message = [event_type, ":", event.data["floor_id"], event.data.get("action", "???")]
            elif event_type in (EVENT_USER_ADDED, EVENT_USER_REMOVED, EVENT_USER_UPDATED):
                message = [event_type, ":", event.data["user_id"]]
            elif event_type == "autoarm_change":
                message = [
                    event_type,
                    ":",
                    event.data["original_state"],
                    "->",
                    event.data["new_state"],
                    " from ",
                    event.data["change_source"],
                ]
            elif any(v in event.data for v in title_fields):
                message = [event_type, ":"] + [event.data[v] for v in title_fields if v in event.data]
            else:
                message = [event_type]

            if event_body:
                flat_event: dict[str, Any] = {k: v for k, v in event.data.items() if k not in _HA_EVENT_BODY_ATTRIBUTE_KEYS}
                event.data = {k: v for k, v in event.data.items() if k in _HA_EVENT_BODY_ATTRIBUTE_KEYS}
                if flat_event:
                    event.data["event.data"] = json.dumps(flat_event, default=_event_data_serializer, indent=2)

            record: LogMessage = self.event_to_log_record(
                event, message_override=message, level_override="INFO", state_only=state_only
            )
            self._buffer.append(record)
            if len(self._buffer) >= self._batch_max_size:
                self._hass.async_create_task(self.flush())
        except Exception as e:
            _LOGGER.error("remote_logger: %s ha_event handler failure %s on %s", self.logger_type, e, event_type)
            self.on_format_error(str(e))

    @abstractmethod
    def event_to_log_record(
        self,
        event: Event,
        message_override: list[str] | None = None,
        level_override: str | None = None,
        state_only: bool = False,
    ) -> LogMessage:
        pass

    @callback
    @abstractmethod
    async def flush(self) -> None:
        pass

    async def flush_loop(self) -> None:
        """Periodically flush buffered log records."""
        self.flushing.set()
        try:
            while self.flushing.is_set():
                await asyncio.sleep(BATCH_FLUSH_INTERVAL_SECONDS)
                await self.flush()
        except asyncio.CancelledError:
            raise

    async def close(self) -> None:
        """Clean up resources (no-op for HTTP-based exporter)."""
        pass

    def on_format_error(self, message: str) -> None:
        self.format_error_count += 1
        self.last_format_error_message = message
        self.last_format_error = dt_util.now()

    def on_posting_error(self, message: str) -> None:
        self.posting_error_count += 1
        self.last_posting_error_message = message
        self.last_posting_error = dt_util.now()

    def on_success(self) -> None:
        self.posting_count += 1
        self.last_posting = dt_util.now()

    def on_event(self) -> None:
        self.event_count += 1
        self.last_event = dt_util.now()

    @abstractmethod
    def log_direct(self, event_name: str, message: str, level: str, attributes: dict[str, Any] | None = None) -> None:
        """Buffer a custom syslog record without requiring a HA Event."""
