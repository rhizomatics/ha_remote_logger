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


Escucha los eventos del registro del sistema de Home Assistant y envía eventos de registro estructurados a un
colector remoto Syslog u OpenTelemetry (OTLP). Opcionalmente reenvía otros eventos de Home Assistant, como
eventos del ciclo de vida, llamadas a servicios, actualizaciones de configuración y cambios de estado.

![Ejemplo de traza de pila OTEL](https://remote-logger.rhizomatics.org.uk/assets/images/otel_stack_trace.png){width=600}

La estructura de los registros se preserva del evento interno de Home Assistant, por lo que los registros multilínea y las trazas de pila se conservan como entradas únicas, a diferencia de los scrapers de consola que crean un evento por línea, y captura correctamente nombres de scripts, números de línea y versiones.

Solo se admite el servidor de Home Assistant con sus componentes personalizados. Los registros de las *apps* (anteriormente llamadas «add-ins»), de HAOS o del supervisor de HA no se proporcionan como eventos capturables, por lo que requieren una solución alternativa. La [LogSpout Home Assistant App](https://github.com/bertbaron/hassio-addons/tree/main/logspout) de Bert Baron cubre estos casos. Puede usarse en combinación con *Remote Logger* para que Home Assistant tenga buenos registros estructurados y todo lo demás quede al menos registrado.

## Instalación

**Remote Logger** es un componente HACS, por lo que primero hay que instalarlo siguiendo las instrucciones de [Getting Started with HACS](https://www.hacs.xyz/docs/use/).

La integración se instala desde la página de integraciones de Home Assistant y **no requiere configuración YAML**.

![Elegir integración](https://remote-logger.rhizomatics.org.uk/assets/images/config_choose.png){width=400}

Sin embargo, sí es necesario un cambio en el YAML de la integración [System Log](https://www.home-assistant.io/integrations/system_log/) de Home Assistant para habilitar el reenvío de eventos `system_log_event`.

```yaml title="Configuración de Home Assistant"
system_log:
    fire_event: true
```

## Open Telemetry (OTEL)

Los registros se envían usando la especificación Open Telemetry Logs a través de una conexión [Open Telemetry Protocol](https://opentelemetry.io/docs/specs/otlp/) (OTLP), como Protobuf o JSON, actualmente solo por HTTP (gRPC podría añadirse en el futuro).

![Configurar OTLP](https://remote-logger.rhizomatics.org.uk/assets/images/config_otel.png){width=480}

Para más información, consulta [OpenTelemetry Logging](https://opentelemetry.io/docs/specs/otel/logs/).

Los registros se recopilan y se envían en lotes.

## Syslog

Los mensajes se envían usando el formato más reciente [RFC5424](https://datatracker.ietf.org/doc/html/rfc5424), con datos estructurados adicionales que utilizan la taxonomía OTEL (ver [Atributos adicionales](#atributos-adicionales)).

Syslog puede enviarse por TCP o UDP.

![Configurar Syslog](https://remote-logger.rhizomatics.org.uk/assets/images/config_syslog.png){width=360}

## Eventos

### Evento System Log

Ten en cuenta el requisito en [Instalación](#instalación) para habilitar este evento,
que no se activa por defecto.

*Remote Logger* excluirá sus propios eventos de registro del flujo, para evitar
la posibilidad de bucles de eventos. Como alternativa, las estadísticas y mensajes de error
están disponibles como entidades de diagnóstico.

#### Atributos adicionales

Los siguientes atributos adicionales, derivados directamente del
evento de registro de Home Assistant, se proporcionan como atributos `STRUCTURED-DATA` de Syslog o atributos OTEL.

* `code.file.path`
* `code.line.number`
* `code.function.name` (este es el valor `logger` de Home Assistant)
* `exception.count`
* `exception.first_occurred`
* `exception.stacktrace`

La taxonomía OTEL se usa tanto para OTEL como para Syslog ya que no existe una taxonomía estándar a este nivel de Syslog.

### Otros eventos

*Remote Logger* puede registrar cualquier evento de Home Assistant y conoce los
principales para crear mensajes más legibles.

Por comodidad, se pueden activar cuatro conjuntos de eventos predefinidos.

| Conjunto | Descripción |
| -------- | ----------- |
| Ciclo de vida | Eventos de inicio y parada del servidor Home Assistant |
| Cambios del núcleo | Carga o descarga de componentes y servicios, configuración reaplicada |
| Actividad del núcleo | Acciones, acciones móviles, scripts, automatizaciones ejecutadas |
| Cambios de estado | Cambios de estado de entidades y entradas del libro de registro, sin atributos ni contexto para evitar entradas de registro demasiado grandes |
| Cambios de estado completos | Cambios de estado de entidades y entradas del libro de registro, completos y sin reducir |

El campo de eventos en formato libre puede usarse como alternativa para seleccionar eventos
específicos de Home Assistant o cualquier otro evento de componentes personalizados.

![Eventos de Home Assistant en OpenObserve](https://remote-logger.rhizomatics.org.uk/assets/images/ha_events_in_openobserve.png){width=720}

## Servidores de registros

Existen infinidad de soluciones para capturar, analizar, agregar y almacenar registros.

Una combinación que funciona bien es [Vector](https://vector.dev) y [GreptimeDb](https://greptime.com) — rápidos, ligeros, de código abierto, personalizables y que funcionan con Docker. Vector admite el registro OTEL y Syslog, con buenas capacidades de remapping para ajustar cada fuente. Luego es fácil integrar registros de servidores Docker, cortafuegos, switches Unifi u otras fuentes en una única línea de tiempo, junto con métricas de servidor y red.


## Entidades de diagnóstico

Se crean y actualizan sensores de Home Assistant para monitorizar la actividad de los registros, así como cualquier error al generar mensajes de registro o al enviarlos a servidores remotos.

![Entidades de diagnóstico](https://remote-logger.rhizomatics.org.uk/assets/images/diagnostic_entities.png){width=480}

##  Rhizomatics Open Source para Home Assistant

### HACS
- [AutoArm](https://autoarm.rhizomatics.org.uk) - Arma y desarma automáticamente los paneles de control de alarma de Home Assistant usando botones físicos, presencia, calendarios, el sol y más
- [Supernotify](https://supernotify.rhizomatics.org.uk) - Notificación unificada para mensajería multicanal sencilla, con potente integración de timbres y cámaras de seguridad.


### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - Integra cámaras ANPR/ALPR de reconocimiento de matrículas a través del sistema de archivos (NAS/FTP) hacia MQTT con análisis opcional de imágenes e integración con la DVLA del Reino Unido.
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Notifica automáticamente por MQTT las actualizaciones de imágenes Docker, con gestión avanzada para extraer versiones y notas de versión de las imágenes, y la opción de activar remotamente la descarga y el reinicio de contenedores desde Home Assistant. También disponible en [PyPI](https://pypi.org/project/updates2mqtt/)

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
