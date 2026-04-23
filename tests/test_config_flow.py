"""Unit tests for config flow helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PROTOCOL
from homeassistant.data_entry_flow import FlowResultType

from custom_components.remote_logger.config_flow import _build_endpoint_url
from custom_components.remote_logger.const import (
    CONF_CUSTOM_EVENTS,
    CONF_LOG_HA_CORE_CHANGES,
    CONF_LOG_HA_LIFECYCLE,
    CONF_USE_TLS,
    DOMAIN,
)
from custom_components.remote_logger.otel.const import ENCODING_JSON

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class TestBuildEndpointUrl:
    def test_http(self) -> None:
        assert _build_endpoint_url("localhost", 4318, False) == "http://localhost:4318/v1/logs"

    def test_https(self) -> None:
        assert _build_endpoint_url("otel.example.com", 443, True) == "https://otel.example.com:443/v1/logs"

    def test_custom_port(self) -> None:
        assert _build_endpoint_url("host", 9999, False) == "http://host:9999/v1/logs"


@pytest.mark.usefixtures("enable_custom_integrations")
class TestOtelConfigFlow:
    async def test_step_user_shows_menu(self, hass: HomeAssistant) -> None:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] == FlowResultType.MENU
        assert "otel" in result["menu_options"]
        assert "syslog" in result["menu_options"]

    async def test_step_otel_shows_form(self, hass: HomeAssistant) -> None:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "otel"})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "otel"

    async def test_step_otel_success(self, hass: HomeAssistant) -> None:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "otel"})
        with patch(
            "custom_components.remote_logger.config_flow.otel_validate",
            new=AsyncMock(return_value={}),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: "localhost",
                    CONF_PORT: 4318,
                    CONF_USE_TLS: False,
                    "encoding": ENCODING_JSON,
                    "batch_max_size": 20,
                    "resource_attributes": "",
                },
            )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "common"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "log_ha_lifecycle": False,
                "ha_standard_events": {
                    "log_ha_core_changes": False,
                    "log_ha_core_activity": False,
                    "log_ha_state_changes": False,
                    "log_ha_full_state_changes": False,
                },
                "custom_events": [],
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "OTLP @ localhost:4318"
        assert result["data"][CONF_HOST] == "localhost"

    async def test_step_otel_connection_error(self, hass: HomeAssistant) -> None:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "otel"})
        with patch(
            "custom_components.remote_logger.config_flow.otel_validate",
            new=AsyncMock(return_value={"base": "cannot_connect"}),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: "badhost",
                    CONF_PORT: 4318,
                    CONF_USE_TLS: False,
                    "encoding": ENCODING_JSON,
                    "batch_max_size": 20,
                    "resource_attributes": "",
                },
            )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"

    async def test_step_otel_basic_auth_stored(self, hass: HomeAssistant) -> None:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "otel"})
        with patch(
            "custom_components.remote_logger.config_flow.otel_validate",
            new=AsyncMock(return_value={}),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: "localhost",
                    CONF_PORT: 4318,
                    CONF_USE_TLS: False,
                    "encoding": ENCODING_JSON,
                    "batch_max_size": 20,
                    "resource_attributes": "",
                    "token_type": "basic",
                    "token": "user:pass",
                },
            )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "common"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "log_ha_lifecycle": False,
                "ha_standard_events": {
                    "log_ha_core_changes": False,
                    "log_ha_core_activity": False,
                    "log_ha_state_changes": False,
                    "log_ha_full_state_changes": False,
                },
                "custom_events": [],
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"]["token_type"] == "basic"  # noqa: S105

    async def test_step_otel_invalid_resource_attributes(self, hass: HomeAssistant) -> None:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "otel"})
        with patch(
            "custom_components.remote_logger.config_flow.otel_validate",
            new=AsyncMock(return_value={}),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: "localhost",
                    CONF_PORT: 4318,
                    CONF_USE_TLS: False,
                    "encoding": ENCODING_JSON,
                    "batch_max_size": 20,
                    "resource_attributes": "bad_format_no_equals",
                },
            )
        assert result["type"] == FlowResultType.FORM
        assert "resource_attributes" in result["errors"]


@pytest.mark.usefixtures("enable_custom_integrations")
class TestSyslogConfigFlow:
    async def test_step_syslog_shows_form(self, hass: HomeAssistant) -> None:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "syslog"})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "syslog"

    async def test_step_syslog_success(self, hass: HomeAssistant) -> None:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "syslog"})
        with patch(
            "custom_components.remote_logger.config_flow.syslog_validate",
            new=AsyncMock(return_value=None),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: "syslog.example.com",
                    CONF_PORT: 514,
                    CONF_PROTOCOL: "udp",
                    CONF_USE_TLS: False,
                    "app_name": "homeassistant",
                    "facility": "local0",
                    "batch_max_size": 20,
                },
            )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "common"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "log_ha_lifecycle": False,
                "ha_standard_events": {
                    "log_ha_core_changes": False,
                    "log_ha_core_activity": False,
                    "log_ha_state_changes": False,
                    "log_ha_full_state_changes": False,
                },
                "custom_events": [],
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert "Syslog @" in result["title"]

    async def test_step_syslog_connection_error(self, hass: HomeAssistant) -> None:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "syslog"})
        with patch(
            "custom_components.remote_logger.config_flow.syslog_validate",
            new=AsyncMock(return_value="cannot_connect"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: "badhost",
                    CONF_PORT: 514,
                    CONF_PROTOCOL: "udp",
                    CONF_USE_TLS: False,
                    "app_name": "homeassistant",
                    "facility": "local0",
                    "batch_max_size": 20,
                },
            )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.usefixtures("enable_custom_integrations")
class TestOptionsFlow:
    def _make_otel_entry(self, extra: dict | None = None) -> ConfigEntry:
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "opt_test"
        entry.domain = DOMAIN
        entry.data = {
            "backend": "otel",
            CONF_HOST: "localhost",
            CONF_PORT: 4318,
            CONF_USE_TLS: False,
            "encoding": ENCODING_JSON,
            "batch_max_size": 100,
            "resource_attributes": "",
            CONF_LOG_HA_LIFECYCLE: False,
            CONF_LOG_HA_CORE_CHANGES: False,
            CONF_CUSTOM_EVENTS: [],
            **(extra or {}),
        }
        entry.options = {}
        return entry

    async def test_options_flow_shows_otel_form(self, hass: HomeAssistant) -> None:
        from custom_components.remote_logger.config_flow import RemoteLoggerOptionsFlow

        entry = self._make_otel_entry()
        flow = RemoteLoggerOptionsFlow(entry)
        flow.hass = hass
        result = await flow.async_step_init(None)
        assert result["type"] == FlowResultType.FORM  # pyright: ignore[reportTypedDictNotRequiredAccess]
        assert result["step_id"] == "otel"  # pyright: ignore[reportTypedDictNotRequiredAccess]

    async def test_options_flow_saves_values(self, hass: HomeAssistant) -> None:
        from custom_components.remote_logger.config_flow import RemoteLoggerOptionsFlow

        entry = self._make_otel_entry()
        flow = RemoteLoggerOptionsFlow(entry)
        flow.hass = hass
        with patch(
            "custom_components.remote_logger.config_flow.otel_validate",
            new=AsyncMock(return_value={}),
        ):
            result: ConfigFlowResult = await flow.async_step_otel({
                CONF_HOST: "newhost",
                CONF_PORT: 4318,
                CONF_USE_TLS: False,
                "encoding": ENCODING_JSON,
                "batch_max_size": 50,
                "resource_attributes": "",
            })
        assert result["type"] == FlowResultType.FORM  # pyright: ignore[reportTypedDictNotRequiredAccess]
        assert result["step_id"] == "events"  # pyright: ignore[reportTypedDictNotRequiredAccess]
        result = await flow.async_step_events({
            CONF_LOG_HA_LIFECYCLE: True,
            CONF_LOG_HA_CORE_CHANGES: False,
            CONF_CUSTOM_EVENTS: ["my_event"],
        })
        assert result["type"] == FlowResultType.CREATE_ENTRY  # pyright: ignore[reportTypedDictNotRequiredAccess]
        assert result["data"][CONF_HOST] == "newhost"  # pyright: ignore[reportTypedDictNotRequiredAccess]
        assert result["data"][CONF_LOG_HA_LIFECYCLE] is True  # pyright: ignore[reportTypedDictNotRequiredAccess]
        assert result["data"][CONF_CUSTOM_EVENTS] == ["my_event"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    async def test_options_flow_prefers_existing_options(self, hass: HomeAssistant) -> None:
        from custom_components.remote_logger.config_flow import RemoteLoggerOptionsFlow

        entry: ConfigEntry[Any] = self._make_otel_entry()
        entry.options[CONF_LOG_HA_LIFECYCLE] = True  # type: ignore
        entry.options[CONF_CUSTOM_EVENTS] = ["zha_event"]  # type: ignore
        flow = RemoteLoggerOptionsFlow(entry)
        flow.hass = hass
        result = await flow.async_step_init(None)
        assert result["type"] == FlowResultType.FORM  # pyright: ignore[reportTypedDictNotRequiredAccess]
        assert result["step_id"] == "otel"  # pyright: ignore[reportTypedDictNotRequiredAccess]

    def _make_syslog_entry(self) -> ConfigEntry:
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "opt_syslog"
        entry.domain = DOMAIN
        entry.data = {
            "backend": "syslog",
            CONF_HOST: "syslog.example.com",
            CONF_PORT: 514,
            "protocol": "udp",
            CONF_USE_TLS: False,
            "app_name": "homeassistant",
            "facility": "local0",
            CONF_LOG_HA_LIFECYCLE: False,
            CONF_LOG_HA_CORE_CHANGES: False,
            CONF_CUSTOM_EVENTS: [],
        }
        entry.options = {}
        return entry

    async def test_options_flow_syslog_shows_syslog_form(self, hass: HomeAssistant) -> None:
        from custom_components.remote_logger.config_flow import RemoteLoggerOptionsFlow

        flow = RemoteLoggerOptionsFlow(self._make_syslog_entry())
        flow.hass = hass
        result = await flow.async_step_init(None)
        assert result["type"] == FlowResultType.FORM  # pyright: ignore[reportTypedDictNotRequiredAccess]
        assert result["step_id"] == "syslog"  # pyright: ignore[reportTypedDictNotRequiredAccess]

    async def test_options_flow_syslog_saves_values(self, hass: HomeAssistant) -> None:
        from custom_components.remote_logger.config_flow import RemoteLoggerOptionsFlow

        flow = RemoteLoggerOptionsFlow(self._make_syslog_entry())
        flow.hass = hass
        with patch(
            "custom_components.remote_logger.config_flow.syslog_validate",
            new=AsyncMock(return_value=None),
        ):
            result = await flow.async_step_syslog({
                CONF_HOST: "newhost",
                CONF_PORT: 514,
                "protocol": "udp",
                CONF_USE_TLS: False,
                "app_name": "homeassistant",
                "facility": "local0",
                "batch_max_size": 10,
            })
        assert result["type"] == FlowResultType.FORM  # pyright: ignore[reportTypedDictNotRequiredAccess]
        assert result["step_id"] == "events"  # pyright: ignore[reportTypedDictNotRequiredAccess]
        result = await flow.async_step_events({
            CONF_LOG_HA_LIFECYCLE: False,
            CONF_LOG_HA_CORE_CHANGES: False,
            CONF_CUSTOM_EVENTS: [],
        })
        assert result["type"] == FlowResultType.CREATE_ENTRY  # pyright: ignore[reportTypedDictNotRequiredAccess]
        assert result["data"][CONF_HOST] == "newhost"  # pyright: ignore[reportTypedDictNotRequiredAccess]
