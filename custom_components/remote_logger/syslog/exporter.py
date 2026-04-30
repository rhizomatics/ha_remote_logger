from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import socket
import ssl
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.system_log import EVENT_SYSTEM_LOG
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PROTOCOL

from custom_components.remote_logger.const import (
    CONF_APP_NAME,
    CONF_BATCH_MAX_SIZE,
    CONF_CLIENT_TIMEOUT,
    CONF_FACILITY,
    CONF_SUPPRESS_SYSTEM_LOG_EVENT_NAME,
    CONF_USE_TLS,
    DEFAULT_CLIENT_TIMEOUT,
)
from custom_components.remote_logger.exporter import LogExporter, LogMessage, LogSubmission
from custom_components.remote_logger.helpers import flatten_event_data, isotimestamp

from .const import (
    DEFAULT_APP_NAME,
    DEFAULT_FACILITY,
    DEFAULT_SYSLOG_SEVERITY,
    PROTOCOL_UDP,
    SYSLOG_FACILITY_MAP,
    SYSLOG_SEVERITY_MAP,
)

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import Event, HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass
class SyslogMessage(LogMessage):
    payload: bytes


class SyslogSubmission(LogSubmission):
    def __init__(self, records: list[SyslogMessage], protocol: str) -> None:
        self.records: list[SyslogMessage] = records
        self.protocol: str = protocol

    def for_display(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "data": cast("str", os.linesep).join(r.payload.decode("utf-8") for r in self.records),
        }


class SyslogExporter(LogExporter):
    """Buffers system_log_event records and flushes them as RFC 5424 syslog messages."""

    logger_type = "syslog"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass)
        self.name = entry.title
        self._in_progress: list[SyslogMessage] = []
        self._lock = asyncio.Lock()

        opts = {**entry.data, **entry.options}

        self._host = opts[CONF_HOST]
        self._port = opts[CONF_PORT]
        self._protocol = opts.get(CONF_PROTOCOL, PROTOCOL_UDP)
        self.destination = (self._host, str(self._port), self._protocol)
        self._use_tls = opts.get(CONF_USE_TLS, False)
        self._app_name = opts.get(CONF_APP_NAME, DEFAULT_APP_NAME)
        facility_name = opts.get(CONF_FACILITY, DEFAULT_FACILITY)
        self._facility = SYSLOG_FACILITY_MAP.get(facility_name, 1)
        self._batch_max_size = opts.get(CONF_BATCH_MAX_SIZE, 10)
        self._client_timeout = opts.get(CONF_CLIENT_TIMEOUT, DEFAULT_CLIENT_TIMEOUT)
        self._suppress_system_log_event_name = opts.get(CONF_SUPPRESS_SYSTEM_LOG_EVENT_NAME, True)
        self._hostname = "-"

        # TCP connection state (lazily created)
        self._tcp_reader: asyncio.StreamReader | None = None
        self._tcp_writer: asyncio.StreamWriter | None = None

        # UDP transport state (lazily created)
        self._udp_transport: asyncio.DatagramTransport | None = None

        self.endpoint_desc = (
            f"syslog://{self._host}:{self._port} ({self._protocol.upper()}"
            f"{'+TLS' if self._use_tls and self._protocol != PROTOCOL_UDP else ''})"
        )
        _LOGGER.info(f"remote_logger: syslog configured for {self.endpoint_desc}")

    def event_to_log_record(
        self,
        event: Event,
        message_override: list[str] | None = None,
        level_override: str | None = None,
        state_only: bool = False,
    ) -> SyslogMessage:
        return self.create_log_record(
            event.data,
            event.event_type,
            event.time_fired,
            message_override=message_override,
            level_override=level_override,
            state_only=state_only,
        )

    def create_log_record(
        self,
        event_data: Mapping[str, Any],
        event_type: str | None = None,
        time_fired: dt.datetime | None = None,
        message_override: list[str] | None = None,
        level_override: str | None = None,
        state_only: bool = False,
    ) -> SyslogMessage:
        """Convert a system_log_event payload to an RFC 5424 syslog message."""
        """
            "name": str
            "message": list(str)
            "level": str
            "source": (str,int)
            "timestamp": float
            "exception": str
            "count": int
            "first_occurred": float
        """
        data = event_data
        level: str = level_override or data.get("level", "INFO").upper()
        severity = SYSLOG_SEVERITY_MAP.get(level, DEFAULT_SYSLOG_SEVERITY)
        pri = self._facility * 8 + severity

        # RFC 3339 timestamp
        timestamp_s: float = data.get("timestamp", time_fired.timestamp() if time_fired else time.time())
        timestamp = isotimestamp(timestamp_s)

        # Message body
        messages: list[str] = message_override or data.get("message", [])
        msg = " ".join(messages) if messages else "-"

        # Structured data with meta info
        sd = "-"
        sd_params: list[str] = []
        if event_type == EVENT_SYSTEM_LOG:
            source = data.get("source")
            if source and isinstance(source, tuple):
                source_path, source_linenum = source
                sd_params.append(f'code.file.path="{_sd_escape(source_path)}"')
                sd_params.append(f'code.line.number="{source_linenum}"')
            logger_name = data.get("name")
            if logger_name:
                sd_params.append(f'code.function.name="{_sd_escape(logger_name)}"')
            if data.get("count"):
                sd_params.append(f'exception.count="{data["count"]}"')
            if data.get("first_occurred"):
                sd_params.append(f'exception.first_occurred="{isotimestamp(data["first_occurred"])}"')

            exception = data.get("exception")
            if exception:
                sd_params.append(f'exception.stacktrace="{data["exception"]}"')
            if not self._suppress_system_log_event_name:
                sd_params.append(f'eventName="{EVENT_SYSTEM_LOG}"')
                msgid: str = EVENT_SYSTEM_LOG
            else:
                msgid = "-"
        else:
            if event_type is not None:
                sd_params.append(f"eventName={event_type}")
            # Use HA event type as MSGID for non-system-log events; "-" otherwise
            msgid = event_type or "-"
            for k, v in data.items():
                for flat_key, flat_val in flatten_event_data(f"event.data.{k}" if k != "event.data" else k, v, state_only):
                    sd_params.append(f'{_sd_escape(flat_key)}="{_sd_escape(str(flat_val))}"')

        if sd_params:
            sd = f"[opentelemetry {' '.join(sd_params)}]"

        # RFC 5424: <PRI>VERSION SP TIMESTAMP SP HOSTNAME SP APP-NAME SP PROCID SP MSGID SP SD [SP MSG]
        # VERSION = 1, PROCID = -
        syslog_line = f"<{pri}>1 {timestamp} {self._hostname} {self._app_name} - {msgid} {sd} {msg}"

        return SyslogMessage(payload=syslog_line.encode("utf-8", errors="replace"))

    def log_direct(self, event_name: str, message: str, level: str, attributes: dict[str, Any] | None = None) -> None:
        """Buffer a custom syslog record without requiring a HA Event."""
        severity = SYSLOG_SEVERITY_MAP.get(level.upper(), DEFAULT_SYSLOG_SEVERITY)
        pri = self._facility * 8 + severity
        timestamp = isotimestamp(time.time())
        sd = "-"
        if attributes:
            sd_params = [f'{_sd_escape(k)}="{_sd_escape(str(v))}"' for k, v in attributes.items()]
            sd = f"[opentelemetry {' '.join(sd_params)}]"
        syslog_line = f"<{pri}>1 {timestamp} {self._hostname} {self._app_name} - {event_name} {sd} {message}"
        record = SyslogMessage(payload=syslog_line.encode("utf-8", errors="replace"))
        self._buffer.append(record)
        self.on_event()
        if len(self._buffer) >= self._batch_max_size:
            self._hass.async_create_task(self.flush())

    async def flush(self) -> None:
        """Flush all buffered log records to the syslog endpoint."""
        records: list[SyslogMessage] | None = None
        async with self._lock:
            if not self._in_progress:
                if not self._buffer:
                    return
                records = cast("list[SyslogMessage]", self._buffer.copy())
                self._buffer.clear()

        try:
            if records:
                self._in_progress = records
            else:
                self._in_progress = [m for m in self._in_progress if not m.sent]

            if self._protocol == PROTOCOL_UDP:
                await self._send_udp(self._in_progress)
            else:
                await self._send_tcp(self._in_progress)
            sent: list[SyslogMessage] = [m for m in self._in_progress if m.sent]
            if sent:
                self.last_sent_payload = SyslogSubmission(sent, protocol=self._protocol)
            self.on_success()
            self._in_progress = [m for m in self._in_progress if not m.sent]
        except Exception as e:
            _LOGGER.exception("remote_logger: unexpected error sending syslog messages")
            self.on_posting_error(str(e))

    async def _send_udp(self, messages: list[SyslogMessage]) -> None:
        """Send syslog messages over UDP."""
        try:
            if self._udp_transport is None or self._udp_transport.is_closing():
                loop = asyncio.get_running_loop()
                self._udp_transport, _ = await loop.create_datagram_endpoint(
                    asyncio.DatagramProtocol,
                    remote_addr=(self._host, self._port),
                )
            for msg in messages:
                self._udp_transport.sendto(msg.payload)
                msg.sent = True
        except OSError as err:
            _LOGGER.warning("remote_logger: failed to send syslog via UDP: %s", err)
            self._udp_transport = None

    async def _send_tcp(self, messages: list[SyslogMessage]) -> None:
        """Send syslog messages over TCP with octet-counting framing (RFC 6587)."""
        try:
            if self._tcp_writer is None or self._tcp_writer.is_closing():
                await self._connect_tcp()

            writer: asyncio.StreamWriter | None = self._tcp_writer
            if writer is None:
                raise OSError("Unable to create TCP writer")  # Set by _connect_tcp above

            for msg in messages:
                # Octet-counting: "LEN SP MSG"
                frame = f"{len(msg.payload)} ".encode("ascii") + msg.payload
                writer.write(frame)
            await writer.drain()
            for msg in messages:
                msg.sent = True
        except (OSError, ConnectionError) as err:
            _LOGGER.warning("remote_logger: failed to send syslog via TCP: %s", err)
            await self._close_tcp()

    async def _connect_tcp(self) -> None:
        """Establish a TCP connection to the syslog server."""
        ssl_ctx: ssl.SSLContext | None = None
        if self._use_tls:
            ssl_ctx = ssl.create_default_context()

        self._tcp_reader, self._tcp_writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port, ssl=ssl_ctx),
            timeout=self._client_timeout,
        )

    async def _close_tcp(self) -> None:
        """Close the TCP connection."""
        if self._tcp_writer is not None:
            with contextlib.suppress(Exception):
                self._tcp_writer.close()
                await self._tcp_writer.wait_closed()
            self._tcp_writer = None
            self._tcp_reader = None

    async def close(self) -> None:
        """Clean up transport resources."""
        if self._udp_transport is not None:
            self._udp_transport.close()
            self._udp_transport = None
        await self._close_tcp()


def _sd_escape(value: str) -> str:
    """Escape special characters for RFC 5424 structured data values."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("]", "\\]")


async def validate(hass: Any, host: str, port: int, protocol: str, use_tls: bool) -> str | None:
    """Test connectivity to a syslog endpoint. Returns error key or None."""
    loop = hass.loop
    try:
        if protocol == PROTOCOL_UDP:
            # Quick UDP test: just resolve and create a socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.setblocking(False)
                await loop.run_in_executor(None, lambda: socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_DGRAM))
            finally:
                sock.close()
        else:
            # TCP: actually connect
            ssl_ctx = True if use_tls else None
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port, ssl=ssl_ctx),
                timeout=10,
            )
            writer.close()
            await writer.wait_closed()
    except (OSError, TimeoutError, ConnectionRefusedError) as err:
        _LOGGER.error("remote_logger: Syslog connect failed: %s", err)
        return "cannot_connect"
    except Exception as err:
        _LOGGER.error("remote_logger: Syslog connect unknown error: %s", err)
        return "unknown"
    return None
