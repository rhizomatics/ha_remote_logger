![Remote Logger](https://remote-logger.rhizomatics.org.uk/assets/images/remote-logger-dark-256x256.png){ align=left }


# Home Assistant Remote Logger

[![Rhizomatics Open Source](https://img.shields.io/badge/rhizomatics%20open%20source-lightseagreen)](https://github.com/rhizomatics) [![hacs][hacsbadge]][hacs]

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/rhizomatics/ha_remote_logger)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/rhizomatics/ha_remote_logger/main.svg)](https://results.pre-commit.ci/latest/github/rhizomatics/ha_remote_logger/main)
![Coverage](https://raw.githubusercontent.com/rhizomatics/ha_remote_logger/refs/heads/badges/badges/coverage.svg)
![Tests](https://raw.githubusercontent.com/rhizomatics/ha_remote_logger/refs/heads/badges/badges/tests.svg)
[![Github Deploy](https://github.com/rhizomatics/ha_remote_logger/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/rhizomatics/ha_remote_logger/actions/workflows/deploy.yml)
[![CodeQL](https://github.com/rhizomatics/ha_remote_logger/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/rhizomatics/ha_remote_logger/actions/workflows/github-code-scanning/codeql)
[![Dependabot Updates](https://github.com/rhizomatics/ha_remote_logger/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/rhizomatics/ha_remote_logger/actions/workflows/dependabot/dependabot-updates)

<br/>
<br/>
<br/>


Listens to Home Assistant system log events and sends structured log events to a remote
Syslog or OpenTelemetry (OTLP) collector. Optionally forwards other Home Assistant events, such
as lifecycle events, service calls, configuration updates, state changes.

![Example OTEL Stack Trace](https://remote-logger.rhizomatics.org.uk/assets/images/otel_stack_trace.png){width=600}

Logs structure is preserved from the Home Assistant internal event, so multi-line logs and stacktraces are preserved as single log entries, unlike console scrapers which will create a log event per line, and will capture script names, line numbers and versions properly.

Only Home Assistant server itself, with its custom components is supported. Logs from *apps* (previously known as 'add-ins'), HAOS or the HA Supervisor aren't provided as events to be captured, so require an alternative solution, like Bert Baron's [LogSpout Home Assistant App](https://github.com/bertbaron/hassio-addons/tree/main/logspout) will cover these. It can be used in combination with *Remote Logger* so that Home Assistant has good structured logs, and everything else is at least logged.

## Installation

**Remote Logger** is a HACS component, so that has to be installed first, using the instruction at [Getting Started with HACS](https://www.hacs.xyz/docs/use/).

The integration installs using the Home Assistant integrations page, and has **no YAML configuration**.

![Choose Integration](https://remote-logger.rhizomatics.org.uk/assets/images/config_choose.png){width=400}

However, a YAML change is required to the Home Assistant [System Log](https://www.home-assistant.io/integrations/system_log/) integration, to enable event forwarding for `system_log_event`.

```yaml title="Home Assistant Configuration"
system_log:
    fire_event: true
```

## Open Telemetry (OTEL)

Logs are sent using Open Telemetry Logs specification over a [Open Telemetry Protocol](https://opentelemetry.io/docs/specs/otlp/)(OTLP) connection, either as Protobuf or JSON, and currently only as HTTP (gRPC may be added in future).

![Configure OTLP](https://remote-logger.rhizomatics.org.uk/assets/images/config_otel.png){width=480}

For more information, see [OpenTelemetry Logging](https://opentelemetry.io/docs/specs/otel/logs/).

Log records are collected and sent in a bundle

## Syslog

Messages are sent using the more recent [RFC5424](https://datatracker.ietf.org/doc/html/rfc5424) format, with additional structured data using OTEL taxonomy (see [Additional Attributes](#additional-attributes)).

Syslog can be sent as TCP or UDP.

![Configure Syslog](https://remote-logger.rhizomatics.org.uk/assets/images/config_syslog.png){width=360}

## Events

### System Log Event

Note the requirement at [Installation](#installation) to enable this event,
which isn't fired by default.

*Remote Logger* will omit its own log events from the stream, to prevent
the possibility of event loops. As an alternative, error stats and messages
are available as diagnostic entities.

#### Additional Attributes

The following additional attributes, derived directly from the
Home Assistant log event, are provided as Syslog `STRUCTURED-DATA` attributes, or OTEL attributes.

* `code.file.path`
* `code.line.number`
* `code.function.name` (this is the `logger` value from Home Assistant)
* `exception.count`
* `exception.first_occurred`
* `exception.stacktrace`

OTEL taxonomy is used for both OTEL and Syslog since there's no standard taxonomy at this
level of Syslog.

### Other Events

*Remote Logger* can log any Home Assistant event, and knows about the core
ones, in order to create a more readable message.

For convenience, four pre-defined bundles of events can be switched on.

| Bundle | Description |
| ------ | ----------- |
| Lifecycle | Home Assistant server start and stop events |
| Core Changes | Components and services loading or unloading, config reapplied |
| Core Activity | Actions, mobile actions, scripts, automations executed |
| State Changes | Entity state changes and log book entries, with states stripped of attributes and context to avoid huge log entries |
| Full State Changes | Entity state changes and log book entries, full and untrimmed |

The free-form event box can be used as an alternative to pick specific
Home Assistant events, or any other custom component events.

![Home Assistant Events in OpenObserve](https://remote-logger.rhizomatics.org.uk/assets/images/ha_events_in_openobserve.png){width=720}

## Log Servers

There are a zillion possible solutions for capturing, analyzing, aggregating and storing logs.

One combination that works well is using [Vector](https://vector.dev) and [GreptimeDb](https://greptime.com) - they are fast, lightweight, open source, customizable and run under Docker. Vector has support for OTEL logging, as well as Syslog, and has good remapping ability to fine tune each source. Its then easy to pull in logs from Docker servers, firewalls, Unifi switches or wherever else into one time-line, as well as server and network metrics.


## Diagnostic Entities

Home Assistant sensors are created and updated to monitor log activity, plus any errors either generating
log messages or posting them to remote servers.

![Diagnostic Entities](https://remote-logger.rhizomatics.org.uk/assets/images/diagnostic_entities.png){width=480}

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
