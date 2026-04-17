import voluptuous as vol
from homeassistant.const import CONF_HEADERS, CONF_HOST, CONF_PATH, CONF_PORT, CONF_TOKEN
from homeassistant.helpers import selector

from custom_components.remote_logger.const import (
    CONF_BATCH_MAX_SIZE,
    CONF_CLIENT_TIMEOUT,
    CONF_ENCODING,
    CONF_RESOURCE_ATTRIBUTES,
    CONF_USE_TLS,
    DEFAULT_BATCH_MAX_SIZE,
    DEFAULT_CLIENT_TIMEOUT,
)

CONF_TOKEN_TYPE = "token_type"  # noqa: S105 # nosec
TOKEN_TYPE_BEARER = "bearer"  # noqa: S105 # nosec
TOKEN_TYPE_BASIC = "basic"  # noqa: S105 # nosec
TOKEN_TYPE_API_KEY = "api_key"  # noqa: S105 # nosec
TOKEN_TYPE_RAW_BASIC = "raw_basic"  # noqa: S105 # nosec
DEFAULT_TOKEN_TYPE = TOKEN_TYPE_BEARER

# OTLP endpoint path
OTLP_LOGS_PATH = "/v1/logs"

# Severity mapping: HA log level string -> (OTLP severityNumber, OTLP severityText)
SEVERITY_MAP: dict[str, tuple[int, str]] = {
    "DEBUG": (5, "DEBUG"),
    "INFO": (9, "INFO"),
    "WARNING": (13, "WARN"),
    "ERROR": (17, "ERROR"),
    "CRITICAL": (21, "FATAL"),
}

DEFAULT_SEVERITY = (9, "INFO")

# OTel defaults
DEFAULT_HTTP_PORT = 4318
DEFAULT_GRPC_PORT = 4317
DEFAULT_USE_TLS = False
DEFAULT_RESOURCE_ATTRIBUTES = ""
ENCODING_JSON = "json"
ENCODING_PROTOBUF = "protobuf"
DEFAULT_ENCODING = ENCODING_PROTOBUF


# Integration metadata (used in InstrumentationScope)
SCOPE_NAME = "homeassistant"
SCOPE_VERSION = "1.0.0"

# Default resource attribute
DEFAULT_SERVICE_NAME = "homeassistant.core"

OTEL_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_PORT, default=DEFAULT_HTTP_PORT): int,
    vol.Optional(CONF_USE_TLS, default=DEFAULT_USE_TLS): bool,
    vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): selector.SelectSelector(
        selector.SelectSelectorConfig(options=[ENCODING_JSON, ENCODING_PROTOBUF])
    ),
    vol.Optional(CONF_BATCH_MAX_SIZE, default=DEFAULT_BATCH_MAX_SIZE): vol.All(int, vol.Range(min=1, max=10000)),
    vol.Optional(CONF_RESOURCE_ATTRIBUTES, default=DEFAULT_RESOURCE_ATTRIBUTES): str,
    vol.Optional(CONF_TOKEN_TYPE, default=DEFAULT_TOKEN_TYPE): selector.SelectSelector(
        selector.SelectSelectorConfig(options=[TOKEN_TYPE_BEARER, TOKEN_TYPE_BASIC, TOKEN_TYPE_RAW_BASIC, TOKEN_TYPE_API_KEY])
    ),
    vol.Optional(CONF_TOKEN, default=""): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    ),
    vol.Optional(CONF_HEADERS, default=[]): selector.TextSelector(selector.TextSelectorConfig(multiple=True)),
    vol.Optional(CONF_PATH, default=OTLP_LOGS_PATH): str,
    vol.Optional(CONF_CLIENT_TIMEOUT, default=DEFAULT_CLIENT_TIMEOUT): vol.All(int, vol.Range(min=1, max=300)),
})

REAUTH_OTEL_DATA_SCHEMA = vol.Schema({
    vol.Optional(CONF_TOKEN_TYPE, default=DEFAULT_TOKEN_TYPE): selector.SelectSelector(
        selector.SelectSelectorConfig(options=[TOKEN_TYPE_BEARER, TOKEN_TYPE_BASIC, TOKEN_TYPE_RAW_BASIC, TOKEN_TYPE_API_KEY])
    ),
    vol.Optional(CONF_TOKEN, default=""): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    ),
})
