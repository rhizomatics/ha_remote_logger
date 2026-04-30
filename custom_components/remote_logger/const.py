"""Constants for the remote_logger integration."""

from homeassistant.const import EntityPlatforms, Platform

DOMAIN = "remote_logger"

PLATFORMS: list[EntityPlatforms] = [Platform.SENSOR]

# Backend selection
CONF_BACKEND = "backend"
BACKEND_OTEL = "otel"
BACKEND_SYSLOG = "syslog"

# Common config entry data keys
CONF_USE_TLS = "use_tls"

# OTel-specific config keys
CONF_RESOURCE_ATTRIBUTES = "resource_attributes"
CONF_ENCODING = "encoding"
CONF_BATCH_MAX_SIZE = "batch_max_size"

# Syslog-specific config keys
CONF_APP_NAME = "app_name"
CONF_FACILITY = "facility"




# Optional HA event subscriptions config keys
CONF_LOG_HA_LIFECYCLE = "log_ha_lifecycle"
CONF_LOG_HA_CORE_CHANGES = "log_ha_core_changes"
CONF_CUSTOM_EVENTS = "custom_events"
CONF_LOG_HA_CORE_ACTIVITY = "log_ha_core_activity"
CONF_LOG_HA_STATE_CHANGES = "log_ha_state_changes"
CONF_LOG_HA_FULL_STATE_CHANGES = "log_ha_full_state_changes"
CONF_LOG_HA_EVENT_BODY = "log_ha_event_body"
CONF_SUPPRESS_SYSTEM_LOG_EVENT_NAME = "suppress_system_log_event_name"

# HA lifecycle event types (EVENT_HOMEASSISTANT_*)
LIFECYCLE_EVENTS: list[str] = [
    "homeassistant_start",
    "homeassistant_started",
    "homeassistant_stop",
    "homeassistant_close",
    "homeassistant_final_write",
]

# HA core change event types
CORE_CHANGE_EVENTS: list[str] = [
    "area_registry_updated",
    "automation_reloaded",
    "category_registry_updated",
    "component_loaded",
    "core_config_updated",
    "data_entry_flow_progressed",
    "device_registry_updated",
    "entity_registry_updated",
    "floor_registry_updated",
    "label_registry_updated",
    "labs_updated",
    "logging_changed",
    "lovelace_updated",
    "panels_updated",
    "repairs_issue_registry_updated",
    "scene_reloaded",
    "service_registered",
    "service_removed",
    "themes_updated",
    "user_added",
    "user_removed",
    "user_updated",
]
CORE_STATE_EVENTS: list[str] = [
    "state_changed",
    "logbook_entry",
]

CORE_ACTIVITY_EVENTS: list[str] = [
    "automation_triggered",
    "persistent_notifications_updated",
    "script_started",
    "call_service",
    "mobile_app_notification_action",
]
BATCH_FLUSH_INTERVAL_SECONDS = 120
DEFAULT_BATCH_MAX_SIZE = 20

DEFAULT_USE_TLS = False

CONF_CLIENT_TIMEOUT = "client_timeout"
DEFAULT_CLIENT_TIMEOUT = 10

CONF_EVENT_BASED_LOGGING = "event_based_logging"
CONF_LOG_LEVEL = "log_level"
DEFAULT_LOG_LEVEL = "INFO"
