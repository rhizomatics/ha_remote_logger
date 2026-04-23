"""Config flow for the remote_logger integration."""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HEADERS, CONF_HOST, CONF_PATH, CONF_PORT, CONF_PROTOCOL, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    BACKEND_OTEL,
    BACKEND_SYSLOG,
    CONF_BACKEND,
    CONF_CUSTOM_EVENTS,
    CONF_ENCODING,
    CONF_LOG_HA_CORE_ACTIVITY,
    CONF_LOG_HA_CORE_CHANGES,
    CONF_LOG_HA_EVENT_BODY,
    CONF_LOG_HA_FULL_STATE_CHANGES,
    CONF_LOG_HA_LIFECYCLE,
    CONF_LOG_HA_STATE_CHANGES,
    CONF_RESOURCE_ATTRIBUTES,
    CONF_USE_TLS,
    DOMAIN,
)
from .otel.const import CONF_TOKEN_TYPE, OTEL_DATA_SCHEMA, OTLP_LOGS_PATH, REAUTH_OTEL_DATA_SCHEMA, TOKEN_TYPE_BEARER
from .otel.exporter import build_auth_header, parse_headers, parse_resource_attributes
from .otel.exporter import validate as otel_validate
from .syslog.const import SYSLOG_DATA_SCHEMA
from .syslog.exporter import validate as syslog_validate

_LOGGER = logging.getLogger(__name__)


def _to_list(value: Any) -> list[str]:
    """Coerce a stored string (comma/newline-separated) or list to a list of strings."""
    if isinstance(value, list):
        return value
    if not value:
        return []
    return [v.strip() for v in re.split(r"[\n,]+", str(value)) if v.strip()]


COMMON_DATA_SCHEMA = vol.Schema({
    vol.Optional(CONF_LOG_HA_LIFECYCLE, default=False): selector.BooleanSelector(),
    vol.Required("ha_standard_events"): section(
        vol.Schema({
            vol.Optional(CONF_LOG_HA_CORE_CHANGES, default=False): selector.BooleanSelector(),
            vol.Optional(CONF_LOG_HA_CORE_ACTIVITY, default=False): selector.BooleanSelector(),
            vol.Optional(CONF_LOG_HA_STATE_CHANGES, default=False): selector.BooleanSelector(),
            vol.Optional(CONF_LOG_HA_FULL_STATE_CHANGES, default=False): selector.BooleanSelector(),
        }),
        {"collapsed": False},
    ),
    vol.Optional(CONF_LOG_HA_EVENT_BODY, default=True): selector.BooleanSelector(),
    vol.Optional(CONF_CUSTOM_EVENTS, default=[]): selector.TextSelector(selector.TextSelectorConfig(multiple=True)),
})


def _build_endpoint_url(host: str, port: int, use_tls: bool, path: str = OTLP_LOGS_PATH) -> str:
    """Build the full OTLP endpoint URL."""
    scheme = "https" if use_tls else "http"
    return f"{scheme}://{host}:{port}{path}"


class OtelLogsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenTelemetry Log Exporter."""

    VERSION = 2

    def __init__(self) -> None:
        super().__init__()
        self._pending_data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return RemoteLoggerOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Show menu to choose backend type."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["otel", "syslog"],
        )

    async def async_step_otel(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle OpenTelemetry OTLP configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            use_tls = user_input[CONF_USE_TLS]
            url = _build_endpoint_url(host, port, use_tls, user_input.get(CONF_PATH, OTLP_LOGS_PATH))

            # Validate header fields format before connecting
            extra_headers: dict[str, str] = {}
            token = user_input.get(CONF_TOKEN, "").strip()
            if token:
                if not use_tls:
                    _LOGGER.warning("remote_logger: token configured without TLS; token will be sent in plain text")
                token_type = user_input.get(CONF_TOKEN_TYPE, TOKEN_TYPE_BEARER)
                extra_headers["Authorization"] = build_auth_header(token, token_type)
            raw_headers = "\n".join(user_input.get(CONF_HEADERS, []))
            if raw_headers:
                try:
                    extra_headers.update(parse_headers(raw_headers))
                except ValueError:
                    errors[CONF_HEADERS] = "invalid_headers"

            # Validate connectivity
            if not errors:
                session = async_get_clientsession(self.hass, verify_ssl=use_tls)
                errors = await otel_validate(session, url, user_input[CONF_ENCODING], extra_headers or None)
            # Validate resource attributes format
            if not errors:
                raw_attrs = user_input.get(CONF_RESOURCE_ATTRIBUTES, "")
                if raw_attrs.strip():
                    try:
                        parse_resource_attributes(raw_attrs)
                    except ValueError:
                        errors[CONF_RESOURCE_ATTRIBUTES] = "invalid_attributes"

            if not errors:
                await self.async_set_unique_id(f"{DOMAIN}_{BACKEND_OTEL}_{host}_{port}")
                self._abort_if_unique_id_configured()
                self._pending_data = {**user_input, CONF_BACKEND: BACKEND_OTEL}
                self._pending_data["_title"] = f"OTLP @ {host}:{port}"
                return await self.async_step_common()

        return self.async_show_form(
            step_id="otel",
            data_schema=self.add_suggested_values_to_schema(OTEL_DATA_SCHEMA, user_input or {}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:  # noqa: ARG002
        """Initiate reauth after authentication failure."""
        return await self.async_step_reauth_otel()

    async def async_step_reauth_otel(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle re-entry of the bearer token after an authentication failure."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input.get(CONF_TOKEN, "").strip()
            extra_headers: dict[str, str] = {}
            if token:
                token_type = user_input.get(CONF_TOKEN_TYPE, TOKEN_TYPE_BEARER)
                extra_headers["Authorization"] = build_auth_header(token, token_type)
            raw_headers = "\n".join(reauth_entry.data.get(CONF_HEADERS, []))
            if raw_headers:
                extra_headers.update(parse_headers(raw_headers))

            url = _build_endpoint_url(
                reauth_entry.data[CONF_HOST],
                reauth_entry.data[CONF_PORT],
                reauth_entry.data[CONF_USE_TLS],
                reauth_entry.data.get(CONF_PATH, OTLP_LOGS_PATH),
            )
            session = async_get_clientsession(self.hass, verify_ssl=reauth_entry.data[CONF_USE_TLS])
            errors = await otel_validate(session, url, reauth_entry.data[CONF_ENCODING], extra_headers or None)
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={
                        CONF_TOKEN: user_input[CONF_TOKEN],
                        CONF_TOKEN_TYPE: user_input.get(CONF_TOKEN_TYPE, TOKEN_TYPE_BEARER),
                    },
                )

        return self.async_show_form(
            step_id="reauth_otel",
            data_schema=self.add_suggested_values_to_schema(REAUTH_OTEL_DATA_SCHEMA, user_input or {}),
            errors=errors,
        )

    async def async_step_syslog(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle Syslog RFC 5424 configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            protocol = user_input[CONF_PROTOCOL]
            use_tls = user_input.get(CONF_USE_TLS, False)

            # Validate connectivity
            error = await syslog_validate(self.hass, host, port, protocol, use_tls)
            if error:
                errors["base"] = error

            if not errors:
                await self.async_set_unique_id(f"{DOMAIN}_{BACKEND_SYSLOG}")
                self._abort_if_unique_id_configured()
                self._pending_data = {**user_input, CONF_BACKEND: BACKEND_SYSLOG}
                self._pending_data["_title"] = f"Syslog @ {host}:{port} ({protocol.upper()})"
                return await self.async_step_common()

        return self.async_show_form(
            step_id="syslog",
            data_schema=self.add_suggested_values_to_schema(SYSLOG_DATA_SCHEMA, user_input or {}),
            errors=errors,
        )

    async def async_step_common(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure common event subscription options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            flat: dict[str, Any] = {k: v for k, v in user_input.items() if not isinstance(v, dict)}
            for v in user_input.values():
                if isinstance(v, dict):
                    flat.update(v)
            if flat.get(CONF_LOG_HA_STATE_CHANGES) and flat.get(CONF_LOG_HA_FULL_STATE_CHANGES):
                errors[CONF_LOG_HA_FULL_STATE_CHANGES] = "state_changes_exclusive"
            else:
                title = self._pending_data.pop("_title")
                return self.async_create_entry(
                    title=title,
                    data={**self._pending_data, **flat},
                )

        return self.async_show_form(
            step_id="common",
            data_schema=self.add_suggested_values_to_schema(COMMON_DATA_SCHEMA, user_input or {}),
            errors=errors,
        )


class RemoteLoggerOptionsFlow(OptionsFlow):
    """Allow editing connection details and event subscriptions after setup."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry
        self._pending_options: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:  # noqa: ARG002
        """Dispatch to the backend-specific connection form."""
        backend = self._config_entry.data.get(CONF_BACKEND, BACKEND_OTEL)
        if backend == BACKEND_SYSLOG:
            return await self.async_step_syslog()
        return await self.async_step_otel()

    async def async_step_otel(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle OTLP connection settings."""
        errors: dict[str, str] = {}
        merged = {**self._config_entry.data, **self._config_entry.options}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            use_tls = user_input[CONF_USE_TLS]
            url = _build_endpoint_url(host, port, use_tls, user_input.get(CONF_PATH, OTLP_LOGS_PATH))

            extra_headers: dict[str, str] = {}
            token = user_input.get(CONF_TOKEN, "").strip()
            if token:
                token_type = user_input.get(CONF_TOKEN_TYPE, TOKEN_TYPE_BEARER)
                extra_headers["Authorization"] = build_auth_header(token, token_type)
            raw_headers = "\n".join(user_input.get(CONF_HEADERS, []))
            if raw_headers:
                try:
                    extra_headers.update(parse_headers(raw_headers))
                except ValueError:
                    errors[CONF_HEADERS] = "invalid_headers"

            if not errors:
                session = async_get_clientsession(self.hass, verify_ssl=use_tls)
                errors = await otel_validate(session, url, user_input[CONF_ENCODING], extra_headers or None)

            if not errors:
                raw_attrs = user_input.get(CONF_RESOURCE_ATTRIBUTES, "")
                if raw_attrs.strip():
                    try:
                        parse_resource_attributes(raw_attrs)
                    except ValueError:
                        errors[CONF_RESOURCE_ATTRIBUTES] = "invalid_attributes"

            if not errors:
                self._pending_options = user_input
                return await self.async_step_events()

        suggested = user_input or {**merged, CONF_HEADERS: _to_list(merged.get(CONF_HEADERS, []))}
        return self.async_show_form(
            step_id="otel",
            data_schema=self.add_suggested_values_to_schema(OTEL_DATA_SCHEMA, suggested),
            errors=errors,
        )

    async def async_step_syslog(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle Syslog connection settings."""
        errors: dict[str, str] = {}
        merged = {**self._config_entry.data, **self._config_entry.options}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            protocol = user_input[CONF_PROTOCOL]
            use_tls = user_input.get(CONF_USE_TLS, False)

            error = await syslog_validate(self.hass, host, port, protocol, use_tls)
            if error:
                errors["base"] = error

            if not errors:
                self._pending_options = user_input
                return await self.async_step_events()

        return self.async_show_form(
            step_id="syslog",
            data_schema=self.add_suggested_values_to_schema(SYSLOG_DATA_SCHEMA, user_input or merged),
            errors=errors,
        )

    async def async_step_events(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle event subscription options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            flat: dict[str, Any] = {k: v for k, v in user_input.items() if not isinstance(v, dict)}
            for v in user_input.values():
                if isinstance(v, dict):
                    flat.update(v)
            if flat.get(CONF_LOG_HA_STATE_CHANGES) and flat.get(CONF_LOG_HA_FULL_STATE_CHANGES):
                errors[CONF_LOG_HA_FULL_STATE_CHANGES] = "state_changes_exclusive"
            else:
                return self.async_create_entry(title="", data={**self._pending_options, **flat})

        merged = {**self._config_entry.data, **self._config_entry.options}
        current = {
            CONF_LOG_HA_LIFECYCLE: merged.get(CONF_LOG_HA_LIFECYCLE, False),
            "ha_standard_events": {
                CONF_LOG_HA_CORE_CHANGES: merged.get(CONF_LOG_HA_CORE_CHANGES, False),
                CONF_LOG_HA_CORE_ACTIVITY: merged.get(CONF_LOG_HA_CORE_ACTIVITY, False),
                CONF_LOG_HA_STATE_CHANGES: merged.get(CONF_LOG_HA_STATE_CHANGES, False),
                CONF_LOG_HA_FULL_STATE_CHANGES: merged.get(CONF_LOG_HA_FULL_STATE_CHANGES, False),
            },
            CONF_LOG_HA_EVENT_BODY: merged.get(CONF_LOG_HA_EVENT_BODY, False),
            CONF_CUSTOM_EVENTS: _to_list(merged.get(CONF_CUSTOM_EVENTS, [])),
        }
        return self.async_show_form(
            step_id="events",
            data_schema=self.add_suggested_values_to_schema(COMMON_DATA_SCHEMA, current),
            errors=errors,
        )
