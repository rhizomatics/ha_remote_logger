"""Unit tests for the protobuf encoder."""

from __future__ import annotations

from custom_components.remote_logger.otel.protobuf_encoder import (
    _encode_any_value,
    _encode_key_value,
    _encode_log_record,
    _encode_resource,
    _encode_string_field,
    _encode_varint,
    _tag,
    encode_export_logs_request,
)

# ---------------------------------------------------------------------------
# Low-level primitives
# ---------------------------------------------------------------------------


class TestEncodeVarint:
    def test_zero(self) -> None:
        assert _encode_varint(0) == b"\x00"

    def test_small(self) -> None:
        assert _encode_varint(1) == b"\x01"
        assert _encode_varint(127) == b"\x7f"

    def test_two_byte(self) -> None:
        # 128 -> 0x80 0x01
        assert _encode_varint(128) == b"\x80\x01"
        # 300 -> 300 = 0b100101100 -> 0xAC 0x02
        assert _encode_varint(300) == b"\xac\x02"

    def test_large(self) -> None:
        result = _encode_varint(123456789)
        # Should be decodable: re-decode to verify
        value = 0
        shift = 0
        for byte in result:
            value |= (byte & 0x7F) << shift
            shift += 7
            if not (byte & 0x80):
                break
        assert value == 123456789


class TestTag:
    def test_field1_varint(self) -> None:
        # field=1, wire_type=0 -> (1<<3)|0 = 8
        assert _tag(1, 0) == b"\x08"

    def test_field1_length_delimited(self) -> None:
        # field=1, wire_type=2 -> (1<<3)|2 = 10
        assert _tag(1, 2) == b"\x0a"

    def test_field2_varint(self) -> None:
        # field=2, wire_type=0 -> (2<<3)|0 = 16
        assert _tag(2, 0) == b"\x10"


class TestEncodeStringField:
    def test_simple_string(self) -> None:
        result = _encode_string_field(1, "hi")
        # tag(1, LEN_DELIMITED) + varint(2) + b"hi"
        assert result == b"\x0a\x02hi"

    def test_empty_string(self) -> None:
        result = _encode_string_field(1, "")
        assert result == b"\x0a\x00"


# ---------------------------------------------------------------------------
# OTLP message encoders
# ---------------------------------------------------------------------------


class TestEncodeAnyValue:
    def test_string_value(self) -> None:
        result = _encode_any_value({"stringValue": "hello"})
        assert b"hello" in result
        assert len(result) > 0

    def test_int_value(self) -> None:
        result = _encode_any_value({"intValue": 42})
        assert len(result) > 0

    def test_bool_true(self) -> None:
        result = _encode_any_value({"boolValue": True})
        assert len(result) > 0

    def test_bool_false(self) -> None:
        result = _encode_any_value({"boolValue": False})
        assert len(result) > 0

    def test_bytes_value(self) -> None:
        result = _encode_any_value({"bytesValue": b"\x01\x02"})
        assert b"\x01\x02" in result

    def test_empty_dict(self) -> None:
        assert _encode_any_value({}) == b""


class TestEncodeKeyValue:
    def test_string_kv(self) -> None:
        kv = {"key": "service.name", "value": {"stringValue": "test"}}
        result = _encode_key_value(kv)
        assert b"service.name" in result
        assert b"test" in result


class TestEncodeResource:
    def test_resource_with_attributes(self) -> None:
        resource = {
            "attributes": [
                {"key": "service.name", "value": {"stringValue": "core"}},
            ]
        }
        result = _encode_resource(resource)
        assert b"service.name" in result
        assert b"core" in result

    def test_empty_resource(self) -> None:
        assert _encode_resource({}) == b""
        assert _encode_resource({"attributes": []}) == b""


class TestEncodeLogRecord:
    def test_full_record(self) -> None:
        record = {
            "timeUnixNano": "1700000000000000000",
            "observedTimeUnixNano": "1700000000000000000",
            "severityNumber": 17,
            "severityText": "ERROR",
            "body": {"stringValue": "test message"},
            "attributes": [
                {"key": "logger.name", "value": {"stringValue": "test"}},
            ],
        }
        result = _encode_log_record(record)
        assert len(result) > 0
        assert b"ERROR" in result
        assert b"test message" in result
        assert b"logger.name" in result

    def test_minimal_record(self) -> None:
        record = {"severityNumber": 9, "body": {"stringValue": "hi"}}
        result = _encode_log_record(record)
        assert len(result) > 0
        assert b"hi" in result

    def test_record_with_trace_and_span_id(self) -> None:
        record = {
            "severityNumber": 9,
            "body": {"stringValue": "traced"},
            "traceId": "0102030405060708090a0b0c0d0e0f10",
            "spanId": "0102030405060708",
        }
        result = _encode_log_record(record)
        assert len(result) > 0
        assert b"\x01\x02\x03\x04\x05\x06\x07\x08" in result


# ---------------------------------------------------------------------------
# Full request encoding
# ---------------------------------------------------------------------------


class TestEncodeExportLogsRequest:
    def test_empty_request(self) -> None:
        result = encode_export_logs_request({"resourceLogs": []})
        assert result == b""

    def test_full_request_produces_bytes(self) -> None:
        request = {
            "resourceLogs": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "core"}},
                        ]
                    },
                    "scopeLogs": [
                        {
                            "scope": {"name": "homeassistant", "version": "1.0.0"},
                            "logRecords": [
                                {
                                    "timeUnixNano": "1700000000000000000",
                                    "severityNumber": 17,
                                    "severityText": "ERROR",
                                    "body": {"stringValue": "something broke"},
                                    "attributes": [],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        result = encode_export_logs_request(request)
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert b"service.name" in result
        assert b"something broke" in result

    def test_request_with_no_resource_logs_key(self) -> None:
        result = encode_export_logs_request({})
        assert result == b""

    def test_multiple_log_records(self) -> None:
        request = {
            "resourceLogs": [
                {
                    "resource": {"attributes": []},
                    "scopeLogs": [
                        {
                            "scope": {"name": "ha"},
                            "logRecords": [
                                {"severityNumber": 9, "body": {"stringValue": "msg1"}},
                                {"severityNumber": 17, "body": {"stringValue": "msg2"}},
                            ],
                        }
                    ],
                }
            ]
        }
        result = encode_export_logs_request(request)
        assert b"msg1" in result
        assert b"msg2" in result
