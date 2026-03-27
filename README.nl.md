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


Luistert naar Home Assistant-systeemloggebeurtenissen en stuurt gestructureerde loggebeurtenissen naar een externe
Syslog- of OpenTelemetry (OTLP)-collector. Optioneel worden andere Home Assistant-gebeurtenissen doorgestuurd, zoals
levenscyclusgebeurtenissen, serviceaanroepen, configuratie-updates en statuswijzigingen.

![Voorbeeld OTEL Stack Trace](https://remote-logger.rhizomatics.org.uk/assets/images/otel_stack_trace.png){width=600}

De logstructuur wordt bewaard vanuit de interne Home Assistant-gebeurtenis, zodat meerdere logregels en stack traces als één logitem worden bewaard — in tegenstelling tot consolescrapers die per regel een gebeurtenis aanmaken. Scriptnamen, regelnummers en versies worden correct vastgelegd.

Alleen de Home Assistant-server zelf met zijn aangepaste componenten wordt ondersteund. Logboeken van *apps* (voorheen bekend als 'add-ins'), HAOS of de HA Supervisor worden niet als vastlegbare gebeurtenissen aangeboden en vereisen een alternatieve oplossing. Bert Barons [LogSpout Home Assistant App](https://github.com/bertbaron/hassio-addons/tree/main/logspout) dekt deze gevallen af. Deze kan samen met *Remote Logger* worden gebruikt zodat Home Assistant goede gestructureerde logboeken heeft en al het overige tenminste wordt vastgelegd.

## Installatie

**Remote Logger** is een HACS-component, die daarom eerst moet worden geïnstalleerd via de instructies op [Getting Started with HACS](https://www.hacs.xyz/docs/use/).

De integratie wordt geïnstalleerd via de Home Assistant-integratiepagina en heeft **geen YAML-configuratie**.

![Integratie kiezen](https://remote-logger.rhizomatics.org.uk/assets/images/config_choose.png){width=400}

Er is echter een YAML-wijziging vereist in de Home Assistant [System Log](https://www.home-assistant.io/integrations/system_log/)-integratie om het doorsturen van `system_log_event` in te schakelen.

```yaml title="Home Assistant-configuratie"
system_log:
    fire_event: true
```

## Open Telemetry (OTEL)

Logboeken worden verzonden via de Open Telemetry Logs-specificatie over een [Open Telemetry Protocol](https://opentelemetry.io/docs/specs/otlp/) (OTLP)-verbinding, als Protobuf of JSON, momenteel alleen via HTTP (gRPC kan in de toekomst worden toegevoegd).

![OTLP configureren](https://remote-logger.rhizomatics.org.uk/assets/images/config_otel.png){width=480}

Zie voor meer informatie [OpenTelemetry Logging](https://opentelemetry.io/docs/specs/otel/logs/).

Logrecords worden verzameld en gebundeld verzonden.

## Syslog

Berichten worden verzonden in het nieuwere [RFC5424](https://datatracker.ietf.org/doc/html/rfc5424)-formaat met aanvullende gestructureerde gegevens op basis van OTEL-taxonomie (zie [Aanvullende attributen](#aanvullende-attributen)).

Syslog kan worden verzonden via TCP of UDP.

![Syslog configureren](https://remote-logger.rhizomatics.org.uk/assets/images/config_syslog.png){width=360}

## Gebeurtenissen

### Systeemloggebeurtenis

Let op de vereiste in [Installatie](#installatie) om deze gebeurtenis in te schakelen,
die standaard niet wordt geactiveerd.

*Remote Logger* sluit eigen loggebeurtenissen uit van de stream om
de mogelijkheid van gebeurtenislussen te voorkomen. Als alternatief zijn foutstatistieken en berichten
beschikbaar als diagnostische entiteiten.

#### Aanvullende attributen

De volgende aanvullende attributen, rechtstreeks afgeleid van de
Home Assistant-loggebeurtenis, worden aangeboden als Syslog `STRUCTURED-DATA`-attributen of OTEL-attributen.

* `code.file.path`
* `code.line.number`
* `code.function.name` (dit is de `logger`-waarde van Home Assistant)
* `exception.count`
* `exception.first_occurred`
* `exception.stacktrace`

OTEL-taxonomie wordt gebruikt voor zowel OTEL als Syslog, omdat er op dit niveau van Syslog geen standaardtaxonomie bestaat.

### Andere gebeurtenissen

*Remote Logger* kan elke Home Assistant-gebeurtenis vastleggen en kent de
kernevenementen om beter leesbare berichten te maken.

Voor het gemak kunnen vier vooraf gedefinieerde gebeurtenisbundels worden ingeschakeld.

| Bundel | Beschrijving |
| ------ | ------------ |
| Levenscyclus | Start- en stopgebeurtenissen van de Home Assistant-server |
| Kernwijzigingen | Laden of lossen van componenten en services, configuratie opnieuw toegepast |
| Kernactiviteit | Acties, mobiele acties, scripts, uitgevoerde automatiseringen |
| Statuswijzigingen | Statuswijzigingen van entiteiten en logboekitems, zonder attributen en context om te grote logitems te vermijden |
| Volledige statuswijzigingen | Statuswijzigingen van entiteiten en logboekitems, volledig en onverkorte |

Het vrije-tekstveld voor gebeurtenissen kan als alternatief worden gebruikt om specifieke
Home Assistant-gebeurtenissen of andere aangepaste componentgebeurtenissen te selecteren.

![Home Assistant-gebeurtenissen in OpenObserve](https://remote-logger.rhizomatics.org.uk/assets/images/ha_events_in_openobserve.png){width=720}

## Logservers

Er zijn talloze oplossingen voor het vastleggen, analyseren, aggregeren en opslaan van logboeken.

Een goede combinatie is [Vector](https://vector.dev) en [GreptimeDb](https://greptime.com) — snel, lichtgewicht, open source, aanpasbaar en draaiend onder Docker. Vector heeft ondersteuning voor OTEL-logboekregistratie en Syslog, met goede herbestemmingsmogelijkheden om elke bron af te stemmen. Vervolgens is het eenvoudig om logboeken van Docker-servers, firewalls, Unifi-switches of andere bronnen samen te brengen in één tijdlijn, aangevuld met server- en netwerkstatistieken.


## Diagnostische entiteiten

Home Assistant-sensoren worden aangemaakt en bijgewerkt om logactiviteit te bewaken, plus eventuele fouten bij het genereren van logberichten of het plaatsen ervan op externe servers.

![Diagnostische entiteiten](https://remote-logger.rhizomatics.org.uk/assets/images/diagnostic_entities.png){width=480}

##  Rhizomatics Open Source voor Home Assistant

### HACS
- [AutoArm](https://autoarm.rhizomatics.org.uk) - Automatisch beveiligen en beveiligen opheffen van Home Assistant-alarmbedieningspanelen via fysieke knoppen, aanwezigheid, agenda's, zon en meer
- [Supernotify](https://supernotify.rhizomatics.org.uk) - Uniforme notificaties voor eenvoudige multi-channel berichten, inclusief krachtige integratie van deurbellen en beveiligingscamera's.


### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - Integreer ANPR/ALPR-kentekenplaatcamera's via het bestandssysteem (NAS/FTP) naar MQTT met optionele beeldanalyse en UK DVLA-integratie.
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Automatisch melden via MQTT bij Docker-image-updates, met geavanceerde verwerking om versies en releasenotes uit images te halen, en de mogelijkheid om containers op afstand te pullen en opnieuw te starten vanuit Home Assistant. Ook beschikbaar op [PyPI](https://pypi.org/project/updates2mqtt/)

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
