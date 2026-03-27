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


Home Assistantのシステムログイベントを監視し、構造化されたログイベントをリモートの
SyslogまたはOpenTelemetry（OTLP）コレクターに送信します。ライフサイクルイベント、サービス呼び出し、設定更新、状態変化など、他のHome Assistantイベントをオプションで転送することもできます。

![OTELスタックトレースの例](https://remote-logger.rhizomatics.org.uk/assets/images/otel_stack_trace.png){width=600}

ログ構造はHome Assistantの内部イベントから保持されるため、複数行のログやスタックトレースは単一のログエントリとして保存されます。コンソールスクレーパーとは異なり、1行につき1イベントを作成することなく、スクリプト名、行番号、バージョンが正確に記録されます。

サポート対象はHome Assistantサーバー本体とそのカスタムコンポーネントのみです。*アプリ*（以前は「アドイン」と呼ばれていた）、HAOS、またはHAスーパーバイザーのログはキャプチャ可能なイベントとして提供されないため、別の解決策が必要です。Bert Baronの[LogSpout Home Assistant App](https://github.com/bertbaron/hassio-addons/tree/main/logspout)がこれらをカバーします。*Remote Logger*と組み合わせて使用することで、Home Assistantが優れた構造化ログを持ち、それ以外もすべて少なくとも記録されるようになります。

## インストール

**Remote Logger**はHACSコンポーネントのため、まず[Getting Started with HACS](https://www.hacs.xyz/docs/use/)の手順に従ってHACSをインストールしてください。

このインテグレーションはHome Assistantのインテグレーションページからインストールでき、**YAMLの設定は不要**です。

![インテグレーションを選択](https://remote-logger.rhizomatics.org.uk/assets/images/config_choose.png){width=400}

ただし、`system_log_event`のイベント転送を有効にするため、Home Assistantの[System Log](https://www.home-assistant.io/integrations/system_log/)インテグレーションのYAMLを変更する必要があります。

```yaml title="Home Assistantの設定"
system_log:
    fire_event: true
```

## Open Telemetry（OTEL）

ログはOpen Telemetry Logs仕様に従い、[Open Telemetry Protocol](https://opentelemetry.io/docs/specs/otlp/)（OTLP）接続を通じてProtobufまたはJSON形式で送信されます。現在はHTTPのみ対応です（将来的にgRPCが追加される可能性があります）。

![OTLPの設定](https://remote-logger.rhizomatics.org.uk/assets/images/config_otel.png){width=480}

詳細は[OpenTelemetry Logging](https://opentelemetry.io/docs/specs/otel/logs/)を参照してください。

ログレコードはまとめてバッチ送信されます。

## Syslog

メッセージはOTELタクソノミーを使用した追加の構造化データ（[追加属性](#追加属性)を参照）とともに、新しい[RFC5424](https://datatracker.ietf.org/doc/html/rfc5424)形式で送信されます。

SyslogはTCPまたはUDPで送信できます。

![Syslogの設定](https://remote-logger.rhizomatics.org.uk/assets/images/config_syslog.png){width=360}

## イベント

### システムログイベント

このイベントはデフォルトでは発火しないため、[インストール](#インストール)の有効化要件に注意してください。

*Remote Logger*はイベントループの発生を防ぐため、自身のログイベントをストリームから除外します。代わりに、エラーの統計とメッセージは診断エンティティとして利用できます。

#### 追加属性

Home Assistantのログイベントから直接取得された以下の追加属性が、Syslogの`STRUCTURED-DATA`属性またはOTEL属性として提供されます。

* `code.file.path`
* `code.line.number`
* `code.function.name`（Home Assistantの`logger`値）
* `exception.count`
* `exception.first_occurred`
* `exception.stacktrace`

SyslogのこのレベルではOTELタクソノミーに標準的な対応物がないため、OTELとSyslogの両方でOTELタクソノミーが使用されます。

### その他のイベント

*Remote Logger*は任意のHome Assistantイベントを記録でき、より読みやすいメッセージを作成するためにコアイベントを把握しています。

利便性のため、4つの事前定義されたイベントバンドルを有効にできます。

| バンドル | 説明 |
| -------- | ---- |
| ライフサイクル | Home Assistantサーバーの起動・停止イベント |
| コア変更 | コンポーネントやサービスのロード・アンロード、設定の再適用 |
| コアアクティビティ | アクション、モバイルアクション、スクリプト、オートメーション実行 |
| 状態変化 | エンティティの状態変化とログブックエントリ（大量のログを避けるため属性・コンテキストなし） |
| 完全な状態変化 | エンティティの状態変化とログブックエントリ（完全・未加工） |

フリーフォームのイベントボックスを代替として使用し、特定のHome Assistantイベントやカスタムコンポーネントのイベントを選択することもできます。

![OpenObserveのHome Assistantイベント](https://remote-logger.rhizomatics.org.uk/assets/images/ha_events_in_openobserve.png){width=720}

## ログサーバー

ログのキャプチャ、分析、集約、保存には無数のソリューションがあります。

うまく機能する組み合わせは[Vector](https://vector.dev)と[GreptimeDb](https://greptime.com)です。高速、軽量、オープンソース、カスタマイズ可能で、Dockerで動作します。VectorはOTELロギングとSyslogをサポートし、各ソースを細かく調整するための優れたリマッピング機能を備えています。その後、DockerサーバーやファイアウォールやUnifiスイッチなどあらゆるソースのログをサーバー・ネットワークメトリクスとともに1つのタイムラインに集約することが容易になります。


## 診断エンティティ

Home Assistantのセンサーが作成・更新され、ログアクティビティを監視するとともに、ログメッセージの生成やリモートサーバーへの送信中に発生したエラーも追跡します。

![診断エンティティ](https://remote-logger.rhizomatics.org.uk/assets/images/diagnostic_entities.png){width=480}

##  Home Assistant向けRhizomaticsオープンソース

### HACS
- [AutoArm](https://autoarm.rhizomatics.org.uk) - 物理ボタン、在宅検知、カレンダー、太陽位置などを使用してHome Assistantのアラームコントロールパネルを自動的にアーム・ディスアームする
- [Supernotify](https://supernotify.rhizomatics.org.uk) - ドアベルやセキュリティカメラの強力な統合を含む、簡単なマルチチャンネルメッセージングのための統合通知。


### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - ファイルシステム（NAS/FTP）経由でANPR/ALPRナンバープレートカメラをMQTTに接続し、オプションの画像分析とUK DVLA連携を提供。
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Dockerイメージの更新をMQTT経由で自動通知。イメージからバージョンやリリースノートを抽出する高度な処理と、Home Assistantからコンテナのリモートプル・再起動オプションも提供。[PyPI](https://pypi.org/project/updates2mqtt/)でも利用可能。

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
