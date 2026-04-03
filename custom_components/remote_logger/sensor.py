"""Binary sensor platform for remote_logger."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.util import slugify

from custom_components.remote_logger.exporter import LogExporter

from .const import DOMAIN
from .remote_logger import REF_EXPORTER

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from custom_components.remote_logger.exporter import LogExporter

from typing import TYPE_CHECKING, Any

from homeassistant.const import EntityCategory


@dataclass(frozen=True, kw_only=True)
class RemoteLoggerDiagnosticEntityDescription(SensorEntityDescription):
    """Describes diagnostic sensor entity."""

    value_fn: Callable[[LogExporter], str | int | float | None]
    attr_fn: Callable[[LogExporter], dict[str, Any]] = lambda _: {}


SENSORS: tuple[RemoteLoggerDiagnosticEntityDescription, ...] = (
    RemoteLoggerDiagnosticEntityDescription(
        key="format_errors",
        translation_key="format_errors",
        native_unit_of_measurement="error",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda logger: logger.format_error_count,
        attr_fn=lambda exporter: {
            "last_error_time": exporter.last_format_error,
            "last_error_message": exporter.last_format_error_message,
        },
    ),
    RemoteLoggerDiagnosticEntityDescription(
        key="posting_errors",
        translation_key="posting_errors",
        native_unit_of_measurement="error",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda logger: logger.posting_error_count,
        attr_fn=lambda exporter: {
            "last_error_time": exporter.last_posting_error,
            "last_error_message": exporter.last_posting_error_message,
        },
    ),
    RemoteLoggerDiagnosticEntityDescription(
        key="events",
        translation_key="events",
        native_unit_of_measurement="event",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda exporter: exporter.event_count,
        attr_fn=lambda exporter: {"last_event_time": exporter.last_event},
    ),
    RemoteLoggerDiagnosticEntityDescription(
        key="postings",
        translation_key="postings",
        native_unit_of_measurement="posting",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda exporter: exporter.posting_count,
        attr_fn=lambda exporter: {"last_posting_time": exporter.last_posting},
    ),
)


class LoggerEntity(SensorEntity):
    """Represent a diagnostic tracking logger."""

    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC  # pyright: ignore[reportIncompatibleVariableOverride]
    _attr_should_poll = True
    _attr_has_entity_name = True

    def __init__(
        self, exporter: LogExporter, description: RemoteLoggerDiagnosticEntityDescription, device_info: DeviceInfo
    ) -> None:
        super().__init__()
        self._exporter: LogExporter = exporter
        self.entity_description: RemoteLoggerDiagnosticEntityDescription = description  # pyright: ignore[reportIncompatibleVariableOverride]
        self._attr_unique_id = slugify(f"{exporter.name}_{description.key}")
        self._attr_device_info = device_info
        self._attr_translation_key = description.translation_key

    @property
    def native_value(self) -> str | int | float | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the state."""
        return self.entity_description.value_fn(self._exporter)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the state attributes."""
        return self.entity_description.attr_fn(self._exporter)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up remote_logger binary sensor from a config entry."""
    exporter: LogExporter = hass.data[DOMAIN][entry.entry_id][REF_EXPORTER]
    device_info = DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Rhizomatics",
        name=f"{exporter.name} Remote Logger",
    )
    async_add_entities(LoggerEntity(exporter, description, device_info) for description in SENSORS)
