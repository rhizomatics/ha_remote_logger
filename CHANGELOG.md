# 1.4.1
- HA event generation more flexible in generating human sensible messages
# 1.4.0
- New action (aka service) to generate events directly
- Logs flushed on Home Assistant shutdown
# 1.3.1
- Improve eventName handling
- Allow state changes to be sent without their attributes
# 1.3.0
- Add any HA event to logging, and use the OTEL `event_name` field for them
    - Pre-bundled events for HA lifecycle and core changes
    - Added float handling to protobuf for event attributes
- Defaults now to expect Python 3.14, in line with Home Assistant from 2026.3 onwards
# 1.2.0
- Choice of Authorization headers for Basic, Basic already encoded and ApiKey
# 1.1.0
- More customization for OTLP, now able to use more platforms, including OpenObserve
    - Custom HTTP headers
    - Bearer token
    - Alternative API endpoint or custom path prefix
# 1.0.0
- Dependencies and docs update for public release
# 0.4.0
- Add Device to bundle entities
# 0.3.0
- Unique names for exporters
# 0.2.0
- Add entities to track incoming events, outgoing postings, errors
- Refactor to common exporter class
# 0.0.5
- Use the OpenTelemetry convention of prefixing Syslog structured data parameters with the non-IANA standard `opentelemetry`
- Messages retried if connection down
