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


Écoute les événements du journal système de Home Assistant et envoie des événements de journal structurés à un
collecteur Syslog ou OpenTelemetry (OTLP) distant. Transmet optionnellement d'autres événements Home Assistant, tels que
les événements du cycle de vie, les appels de services, les mises à jour de configuration et les changements d'état.

![Exemple de trace de pile OTEL](https://remote-logger.rhizomatics.org.uk/assets/images/otel_stack_trace.png){width=600}

La structure des journaux est préservée depuis l'événement interne de Home Assistant, de sorte que les journaux multi-lignes et les traces de pile sont conservés comme des entrées uniques, contrairement aux scrapers de console qui créent un événement par ligne, et capturent correctement les noms de scripts, les numéros de lignes et les versions.

Seul le serveur Home Assistant lui-même, avec ses composants personnalisés, est pris en charge. Les journaux des *apps* (anciennement appelées « add-ins »), de HAOS ou du superviseur HA ne sont pas fournis comme événements captables et nécessitent donc une solution alternative. [LogSpout Home Assistant App](https://github.com/bertbaron/hassio-addons/tree/main/logspout) de Bert Baron couvre ces cas. Elle peut être utilisée en combinaison avec *Remote Logger* afin que Home Assistant dispose de journaux structurés de qualité, et que tout le reste soit au moins enregistré.

## Installation

**Remote Logger** est un composant HACS, qui doit donc être installé en premier en suivant les instructions de [Getting Started with HACS](https://www.hacs.xyz/docs/use/).

L'intégration s'installe depuis la page des intégrations de Home Assistant et **ne nécessite aucune configuration YAML**.

![Choisir l'intégration](https://remote-logger.rhizomatics.org.uk/assets/images/config_choose.png){width=400}

Une modification YAML est cependant requise dans l'intégration [System Log](https://www.home-assistant.io/integrations/system_log/) de Home Assistant pour activer le transfert d'événements `system_log_event`.

```yaml title="Configuration Home Assistant"
system_log:
    fire_event: true
```

## Open Telemetry (OTEL)

Les journaux sont envoyés selon la spécification Open Telemetry Logs via une connexion [Open Telemetry Protocol](https://opentelemetry.io/docs/specs/otlp/) (OTLP), en Protobuf ou JSON, et actuellement uniquement en HTTP (gRPC pourra être ajouté à l'avenir).

![Configurer OTLP](https://remote-logger.rhizomatics.org.uk/assets/images/config_otel.png){width=480}

Pour plus d'informations, voir [OpenTelemetry Logging](https://opentelemetry.io/docs/specs/otel/logs/).

Les enregistrements de journaux sont collectés et envoyés en lot.

## Syslog

Les messages sont envoyés au format plus récent [RFC5424](https://datatracker.ietf.org/doc/html/rfc5424), avec des données structurées supplémentaires utilisant la taxonomie OTEL (voir [Attributs supplémentaires](#attributs-supplémentaires)).

Syslog peut être envoyé en TCP ou UDP.

![Configurer Syslog](https://remote-logger.rhizomatics.org.uk/assets/images/config_syslog.png){width=360}

## Événements

### Événement System Log

Notez l'exigence à la section [Installation](#installation) pour activer cet événement,
qui n'est pas déclenché par défaut.

*Remote Logger* exclura ses propres événements de journal du flux, pour éviter
tout risque de boucle d'événements. En alternative, les statistiques et messages d'erreur
sont disponibles sous forme d'entités de diagnostic.

#### Attributs supplémentaires

Les attributs supplémentaires suivants, dérivés directement de
l'événement de journal Home Assistant, sont fournis comme attributs `STRUCTURED-DATA` Syslog ou attributs OTEL.

* `code.file.path`
* `code.line.number`
* `code.function.name` (il s'agit de la valeur `logger` de Home Assistant)
* `exception.count`
* `exception.first_occurred`
* `exception.stacktrace`

La taxonomie OTEL est utilisée à la fois pour OTEL et Syslog car il n'existe pas de taxonomie standard à ce niveau de Syslog.

### Autres événements

*Remote Logger* peut journaliser n'importe quel événement Home Assistant et connaît les
événements principaux afin de créer un message plus lisible.

Par commodité, quatre ensembles d'événements prédéfinis peuvent être activés.

| Ensemble | Description |
| -------- | ----------- |
| Cycle de vie | Événements de démarrage et d'arrêt du serveur Home Assistant |
| Modifications du cœur | Chargement ou déchargement de composants et services, configuration réappliquée |
| Activité du cœur | Actions, actions mobiles, scripts, automations exécutés |
| Changements d'état | Changements d'état des entités et entrées du journal, avec les états dépourvus d'attributs et de contexte pour éviter des entrées de journal trop volumineuses |
| Changements d'état complets | Changements d'état des entités et entrées du journal, complets et non réduits |

Le champ d'événements en format libre peut être utilisé comme alternative pour choisir des
événements Home Assistant spécifiques ou tout autre événement de composant personnalisé.

![Événements Home Assistant dans OpenObserve](https://remote-logger.rhizomatics.org.uk/assets/images/ha_events_in_openobserve.png){width=720}

## Serveurs de journaux

Il existe une multitude de solutions pour capturer, analyser, agréger et stocker les journaux.

Une combinaison qui fonctionne bien est [Vector](https://vector.dev) et [GreptimeDb](https://greptime.com) — rapides, légers, open source, personnalisables et fonctionnant sous Docker. Vector prend en charge la journalisation OTEL ainsi que Syslog, avec de bonnes capacités de remapping pour affiner chaque source. Il est ensuite facile d'intégrer les journaux de serveurs Docker, de pare-feu, de commutateurs Unifi ou d'autres sources dans une seule chronologie, ainsi que des métriques de serveur et de réseau.


## Entités de diagnostic

Des capteurs Home Assistant sont créés et mis à jour pour surveiller l'activité des journaux, ainsi que les erreurs éventuelles lors de la génération des messages de journal ou de leur envoi aux serveurs distants.

![Entités de diagnostic](https://remote-logger.rhizomatics.org.uk/assets/images/diagnostic_entities.png){width=480}

##  Rhizomatics Open Source pour Home Assistant

### HACS
- [AutoArm](https://autoarm.rhizomatics.org.uk) - Arme et désarme automatiquement les panneaux de contrôle d'alarme de Home Assistant à l'aide de boutons physiques, de la présence, de calendriers, du soleil et plus encore
- [Supernotify](https://supernotify.rhizomatics.org.uk) - Notification unifiée pour une messagerie multi-canal simple, avec une intégration puissante des sonnettes et des caméras de sécurité.


### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - Intègre les caméras ANPR/ALPR de reconnaissance de plaques via le système de fichiers (NAS/FTP) vers MQTT avec analyse d'image optionnelle et intégration DVLA UK.
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Notifie automatiquement via MQTT les mises à jour d'images Docker, avec une gestion avancée pour extraire les versions et les notes de version des images, et la possibilité de déclencher à distance le pull et le redémarrage des conteneurs depuis Home Assistant. Disponible également sur [PyPI](https://pypi.org/project/updates2mqtt/)

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
