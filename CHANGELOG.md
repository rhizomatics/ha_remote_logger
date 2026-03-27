# 1.4.8
- Translations for Dutch, French, German, Hindi, Italian, Japanese, Polish, Portuguese, Simplified Chinese and Spanish
- Vertalingen voor Nederlands, Traductions en français, Übersetzungen auf Deutsch, हिंदी में अनुवाद, Traduzioni in italiano, 日本語の翻訳, Tłumaczenia po polsku, Traduções em português, 简体中文翻译 en traducciones al español
# 1.4.7
- Prettify flattened HA event json
- Rename component in manifest to match public naming
# 1.4.6
- HA event serialization tuning
# 1.4.5
- Retain `message` and `event` for simplified HA events
# 1.4.4
- Update to translation strings for new event serialization
- French and Italian translations added
- Don't double log events generated via system_log.event
# 1.4.3
- Option to serialize Home Assistant events into a single string, other than entity_id, component, domain to avoid schema pollution on log aggregators
# 1.4.2
- Event generation fixes and more tests
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
