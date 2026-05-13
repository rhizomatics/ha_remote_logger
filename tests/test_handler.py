"""Unit tests for ExportingLogHandler."""

from __future__ import annotations

import datetime as dt
import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from custom_components.remote_logger.handler import ExportingLogHandler

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class TestExportingLogHandler:
    @pytest.fixture
    def mock_handler(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def log_handler(self, hass: HomeAssistant, mock_handler: MagicMock) -> ExportingLogHandler:
        return ExportingLogHandler(hass, mock_handler)

    def _record(self, name: str, level: int = logging.ERROR, msg: str = "test") -> logging.LogRecord:
        return logging.LogRecord(name=name, level=level, pathname="test.py", lineno=1, msg=msg, args=(), exc_info=None)

    def test_emit_skips_own_namespace(self, log_handler: ExportingLogHandler, mock_handler: MagicMock) -> None:
        log_handler.emit(self._record("custom_components.remote_logger"))
        log_handler.emit(self._record("custom_components.remote_logger.otel.exporter"))
        mock_handler.assert_not_called()

    def test_emit_calls_handler_for_other_loggers(self, log_handler: ExportingLogHandler, mock_handler: MagicMock) -> None:
        log_handler.emit(self._record("homeassistant.components.sensor"))
        mock_handler.assert_called_once()

    def test_emit_does_not_skip_other_custom_components(self, log_handler: ExportingLogHandler, mock_handler: MagicMock) -> None:
        log_handler.emit(self._record("custom_components.other_integration"))
        mock_handler.assert_called_once()

    def test_emit_passes_dict_and_time_fired(self, log_handler: ExportingLogHandler, mock_handler: MagicMock) -> None:
        log_handler.emit(self._record("homeassistant.core"))
        args, kwargs = mock_handler.call_args
        assert isinstance(args[0], dict)
        assert "time_fired" in kwargs
        assert isinstance(kwargs["time_fired"], dt.datetime)

    def test_emit_time_fired_matches_record_created(self, log_handler: ExportingLogHandler, mock_handler: MagicMock) -> None:
        record = self._record("homeassistant.core")
        log_handler.emit(record)
        _, kwargs = mock_handler.call_args
        expected = dt.datetime.fromtimestamp(record.created, tz=log_handler.tz)
        assert kwargs["time_fired"] == expected
