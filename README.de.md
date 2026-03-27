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


Lauscht auf Home Assistant-Systemprotokollereignisse und sendet strukturierte Protokollereignisse an einen entfernten
Syslog- oder OpenTelemetry (OTLP)-Collector. Optional werden weitere Home Assistant-Ereignisse weitergeleitet, z. B.
Lebenszyklusereignisse, Dienstaufrufe, Konfigurationsaktualisierungen und Zustandsänderungen.

![Beispiel OTEL Stack Trace](https://remote-logger.rhizomatics.org.uk/assets/images/otel_stack_trace.png){width=600}

Die Protokollstruktur wird vom internen Home Assistant-Ereignis beibehalten, sodass mehrzeilige Protokolle und Stack Traces als einzelne Protokolleinträge erhalten bleiben – im Gegensatz zu Console-Scrapern, die pro Zeile ein Ereignis erstellen. Skriptnamen, Zeilennummern und Versionen werden dabei korrekt erfasst.

Unterstützt wird ausschließlich der Home Assistant-Server selbst mit seinen benutzerdefinierten Komponenten. Protokolle von *Apps* (ehemals „Add-ins"), HAOS oder dem HA-Supervisor werden nicht als erfassbare Ereignisse bereitgestellt und erfordern daher eine alternative Lösung. Bert Barons [LogSpout Home Assistant App](https://github.com/bertbaron/hassio-addons/tree/main/logspout) deckt diese Fälle ab. Sie kann in Kombination mit *Remote Logger* verwendet werden, damit Home Assistant gute strukturierte Protokolle hat und alles andere zumindest protokolliert wird.

## Installation

**Remote Logger** ist eine HACS-Komponente, die daher zuerst installiert werden muss. Die Anleitung dazu findet sich unter [Getting Started with HACS](https://www.hacs.xyz/docs/use/).

Die Integration wird über die Home Assistant-Integrationsseite installiert und erfordert **keine YAML-Konfiguration**.

![Integration auswählen](https://remote-logger.rhizomatics.org.uk/assets/images/config_choose.png){width=400}

Allerdings ist eine YAML-Änderung an der Home Assistant-Integration [System Log](https://www.home-assistant.io/integrations/system_log/) erforderlich, um die Ereignisweiterleitung für `system_log_event` zu aktivieren.

```yaml title="Home Assistant-Konfiguration"
system_log:
    fire_event: true
```

## Open Telemetry (OTEL)

Protokolle werden gemäß der Open Telemetry Logs-Spezifikation über eine [Open Telemetry Protocol](https://opentelemetry.io/docs/specs/otlp/)-Verbindung (OTLP) gesendet, entweder als Protobuf oder JSON, derzeit ausschließlich über HTTP (gRPC könnte in Zukunft hinzugefügt werden).

![OTLP konfigurieren](https://remote-logger.rhizomatics.org.uk/assets/images/config_otel.png){width=480}

Weitere Informationen finden sich unter [OpenTelemetry Logging](https://opentelemetry.io/docs/specs/otel/logs/).

Protokolleinträge werden gesammelt und gebündelt gesendet.

## Syslog

Nachrichten werden im neueren Format [RFC5424](https://datatracker.ietf.org/doc/html/rfc5424) mit zusätzlichen strukturierten Daten gemäß OTEL-Taxonomie gesendet (siehe [Zusätzliche Attribute](#zusätzliche-attribute)).

Syslog kann per TCP oder UDP übertragen werden.

![Syslog konfigurieren](https://remote-logger.rhizomatics.org.uk/assets/images/config_syslog.png){width=360}

## Ereignisse

### System-Log-Ereignis

Hinweis auf die Anforderung unter [Installation](#installation), dieses Ereignis zu aktivieren,
das standardmäßig nicht ausgelöst wird.

*Remote Logger* schließt eigene Protokollereignisse aus dem Stream aus, um
mögliche Ereignisschleifen zu verhindern. Alternativ stehen Fehlerstatistiken und -meldungen
als diagnostische Entitäten zur Verfügung.

#### Zusätzliche Attribute

Die folgenden zusätzlichen Attribute, die direkt aus dem
Home Assistant-Protokollereignis abgeleitet werden, stehen als Syslog-`STRUCTURED-DATA`-Attribute oder OTEL-Attribute zur Verfügung.

* `code.file.path`
* `code.line.number`
* `code.function.name` (dies ist der `logger`-Wert von Home Assistant)
* `exception.count`
* `exception.first_occurred`
* `exception.stacktrace`

Die OTEL-Taxonomie wird sowohl für OTEL als auch für Syslog verwendet, da es auf dieser Syslog-Ebene keine standardisierte Taxonomie gibt.

### Weitere Ereignisse

*Remote Logger* kann beliebige Home Assistant-Ereignisse protokollieren und kennt die
wichtigsten davon, um lesbarere Meldungen zu erzeugen.

Der Einfachheit halber können vier vordefinierte Ereignis-Bundles aktiviert werden.

| Bundle | Beschreibung |
| ------ | ------------ |
| Lebenszyklus | Start- und Stoppereignisse des Home Assistant-Servers |
| Kernänderungen | Laden oder Entladen von Komponenten und Diensten, Konfiguration neu angewendet |
| Kernaktivität | Aktionen, mobile Aktionen, Skripte, ausgeführte Automatisierungen |
| Zustandsänderungen | Zustandsänderungen von Entitäten und Logbucheinträge, ohne Attribute und Kontext um übermäßig große Protokolleinträge zu vermeiden |
| Vollständige Zustandsänderungen | Zustandsänderungen von Entitäten und Logbucheinträge, vollständig und ungekürzt |

Das Freitextfeld für Ereignisse kann alternativ verwendet werden, um spezifische
Home Assistant-Ereignisse oder andere Ereignisse benutzerdefinierter Komponenten auszuwählen.

![Home Assistant-Ereignisse in OpenObserve](https://remote-logger.rhizomatics.org.uk/assets/images/ha_events_in_openobserve.png){width=720}

## Protokoll-Server

Es gibt unzählige Lösungen zum Erfassen, Analysieren, Aggregieren und Speichern von Protokollen.

Eine gut funktionierende Kombination ist [Vector](https://vector.dev) und [GreptimeDb](https://greptime.com) – schnell, schlank, Open Source, anpassbar und unter Docker lauffähig. Vector unterstützt OTEL-Logging sowie Syslog und bietet gute Remapping-Möglichkeiten zur Feinabstimmung jeder Quelle. Protokolle von Docker-Servern, Firewalls, Unifi-Switches oder anderen Quellen lassen sich dann einfach in einer gemeinsamen Zeitachse zusammenführen, zusammen mit Server- und Netzwerkmetriken.


## Diagnostische Entitäten

Home Assistant-Sensoren werden erstellt und aktualisiert, um die Protokollaktivität sowie etwaige Fehler bei der Erzeugung von Protokollmeldungen oder deren Übertragung an entfernte Server zu überwachen.

![Diagnostische Entitäten](https://remote-logger.rhizomatics.org.uk/assets/images/diagnostic_entities.png){width=480}

##  Rhizomatics Open Source für Home Assistant

### HACS
- [AutoArm](https://autoarm.rhizomatics.org.uk) - Scharf- und Unscharfschalten von Home Assistant-Alarmzentralen automatisch mit physischen Tasten, Anwesenheit, Kalendern, Sonnenstand und mehr
- [Supernotify](https://supernotify.rhizomatics.org.uk) - Einheitliche Benachrichtigung für einfaches Multi-Kanal-Messaging, einschließlich leistungsstarker Türklingel- und Sicherheitskameraintegration.


### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - Integration von ANPR/ALPR-Kennzeichenkameras über Dateisystem (NAS/FTP) nach MQTT mit optionaler Bildanalyse und UK DVLA-Integration.
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Automatische Benachrichtigung per MQTT über Docker-Image-Updates, mit erweiterter Verarbeitung zur Extraktion von Versionen und Release-Notes aus Images sowie der Möglichkeit, Container-Pulls und -Neustarts aus Home Assistant heraus fernzusteuern. Auch verfügbar auf [PyPI](https://pypi.org/project/updates2mqtt/)

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
