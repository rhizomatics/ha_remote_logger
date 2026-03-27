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


Home Assistant सिस्टम लॉग इवेंट को सुनता है और संरचित लॉग इवेंट को एक दूरस्थ
Syslog या OpenTelemetry (OTLP) कलेक्टर को भेजता है। वैकल्पिक रूप से अन्य Home Assistant इवेंट भी अग्रेषित करता है, जैसे
जीवनचक्र इवेंट, सर्विस कॉल, कॉन्फ़िगरेशन अपडेट और स्थिति परिवर्तन।

![OTEL स्टैक ट्रेस उदाहरण](https://remote-logger.rhizomatics.org.uk/assets/images/otel_stack_trace.png){width=600}

लॉग संरचना Home Assistant के आंतरिक इवेंट से संरक्षित रहती है, इसलिए मल्टी-लाइन लॉग और स्टैक ट्रेस एकल लॉग प्रविष्टियों के रूप में सहेजे जाते हैं — कंसोल स्क्रेपर्स के विपरीत जो प्रति पंक्ति एक इवेंट बनाते हैं। स्क्रिप्ट नाम, लाइन नंबर और संस्करण सही ढंग से कैप्चर किए जाते हैं।

केवल Home Assistant सर्वर और उसके कस्टम कंपोनेंट समर्थित हैं। *ऐप्स* (पहले 'add-ins' के नाम से जाने जाते थे), HAOS या HA सुपरवाइज़र के लॉग कैप्चर करने योग्य इवेंट के रूप में उपलब्ध नहीं हैं, इसलिए इनके लिए वैकल्पिक समाधान की आवश्यकता है। Bert Baron का [LogSpout Home Assistant App](https://github.com/bertbaron/hassio-addons/tree/main/logspout) इन मामलों को कवर करता है। इसे *Remote Logger* के साथ संयोजन में उपयोग किया जा सकता है ताकि Home Assistant के पास अच्छे संरचित लॉग हों और बाकी सब कुछ कम से कम लॉग हो।

## इंस्टॉलेशन

**Remote Logger** एक HACS कंपोनेंट है, इसलिए पहले [Getting Started with HACS](https://www.hacs.xyz/docs/use/) के निर्देशों का पालन करके HACS इंस्टॉल करें।

यह इंटीग्रेशन Home Assistant की इंटीग्रेशन पेज से इंस्टॉल होता है और इसमें **कोई YAML कॉन्फ़िगरेशन नहीं** है।

![इंटीग्रेशन चुनें](https://remote-logger.rhizomatics.org.uk/assets/images/config_choose.png){width=400}

हालांकि, `system_log_event` के इवेंट फॉरवर्डिंग को सक्षम करने के लिए Home Assistant के [System Log](https://www.home-assistant.io/integrations/system_log/) इंटीग्रेशन में एक YAML परिवर्तन आवश्यक है।

```yaml title="Home Assistant कॉन्फ़िगरेशन"
system_log:
    fire_event: true
```

## Open Telemetry (OTEL)

लॉग Open Telemetry Logs स्पेसिफिकेशन के अनुसार एक [Open Telemetry Protocol](https://opentelemetry.io/docs/specs/otlp/) (OTLP) कनेक्शन के माध्यम से Protobuf या JSON के रूप में भेजे जाते हैं, वर्तमान में केवल HTTP के माध्यम से (भविष्य में gRPC जोड़ा जा सकता है)।

![OTLP कॉन्फ़िगर करें](https://remote-logger.rhizomatics.org.uk/assets/images/config_otel.png){width=480}

अधिक जानकारी के लिए [OpenTelemetry Logging](https://opentelemetry.io/docs/specs/otel/logs/) देखें।

लॉग रिकॉर्ड एकत्र किए जाते हैं और बैच में भेजे जाते हैं।

## Syslog

संदेश नए [RFC5424](https://datatracker.ietf.org/doc/html/rfc5424) फॉर्मेट में OTEL टैक्सोनॉमी (देखें [अतिरिक्त एट्रिब्यूट](#अतिरिक्त-एट्रिब्यूट)) का उपयोग करके अतिरिक्त संरचित डेटा के साथ भेजे जाते हैं।

Syslog TCP या UDP के माध्यम से भेजा जा सकता है।

![Syslog कॉन्फ़िगर करें](https://remote-logger.rhizomatics.org.uk/assets/images/config_syslog.png){width=360}

## इवेंट

### सिस्टम लॉग इवेंट

[इंस्टॉलेशन](#इंस्टॉलेशन) में इस इवेंट को सक्षम करने की आवश्यकता पर ध्यान दें,
जो डिफ़ॉल्ट रूप से फायर नहीं होता।

*Remote Logger* इवेंट लूप की संभावना को रोकने के लिए अपने स्वयं के लॉग इवेंट को स्ट्रीम से बाहर रखेगा। विकल्प के रूप में, त्रुटि आँकड़े और संदेश डायग्नोस्टिक एंटिटी के रूप में उपलब्ध हैं।

#### अतिरिक्त एट्रिब्यूट

निम्नलिखित अतिरिक्त एट्रिब्यूट, सीधे Home Assistant लॉग इवेंट से प्राप्त,
Syslog `STRUCTURED-DATA` एट्रिब्यूट या OTEL एट्रिब्यूट के रूप में प्रदान किए जाते हैं।

* `code.file.path`
* `code.line.number`
* `code.function.name` (यह Home Assistant का `logger` मान है)
* `exception.count`
* `exception.first_occurred`
* `exception.stacktrace`

OTEL टैक्सोनॉमी OTEL और Syslog दोनों के लिए उपयोग की जाती है क्योंकि Syslog के इस स्तर पर कोई मानक टैक्सोनॉमी नहीं है।

### अन्य इवेंट

*Remote Logger* किसी भी Home Assistant इवेंट को लॉग कर सकता है और अधिक पठनीय संदेश बनाने के लिए मुख्य इवेंट को जानता है।

सुविधा के लिए, चार पूर्व-परिभाषित इवेंट बंडल चालू किए जा सकते हैं।

| बंडल | विवरण |
| ----- | ------ |
| जीवनचक्र | Home Assistant सर्वर स्टार्ट और स्टॉप इवेंट |
| कोर परिवर्तन | कंपोनेंट और सर्विस लोडिंग या अनलोडिंग, कॉन्फ़िगरेशन पुनः लागू |
| कोर गतिविधि | एक्शन, मोबाइल एक्शन, स्क्रिप्ट, ऑटोमेशन निष्पादन |
| स्थिति परिवर्तन | एंटिटी स्थिति परिवर्तन और लॉग बुक प्रविष्टियाँ, विशाल लॉग प्रविष्टियों से बचने के लिए एट्रिब्यूट और संदर्भ के बिना |
| पूर्ण स्थिति परिवर्तन | एंटिटी स्थिति परिवर्तन और लॉग बुक प्रविष्टियाँ, पूर्ण और बिना कटौती के |

फ्री-फॉर्म इवेंट बॉक्स का उपयोग विशिष्ट Home Assistant इवेंट या किसी अन्य कस्टम कंपोनेंट इवेंट को चुनने के विकल्प के रूप में किया जा सकता है।

![OpenObserve में Home Assistant इवेंट](https://remote-logger.rhizomatics.org.uk/assets/images/ha_events_in_openobserve.png){width=720}

## लॉग सर्वर

लॉग कैप्चर करने, विश्लेषण करने, एकत्रित करने और संग्रहीत करने के लिए अनगिनत समाधान उपलब्ध हैं।

एक अच्छा संयोजन है [Vector](https://vector.dev) और [GreptimeDb](https://greptime.com) — तेज़, हल्के, ओपन सोर्स, अनुकूलनीय और Docker के तहत चलने वाले। Vector में OTEL लॉगिंग और Syslog का समर्थन है, साथ ही प्रत्येक स्रोत को ठीक करने के लिए अच्छी रीमैपिंग क्षमता है। इसके बाद Docker सर्वर, फ़ायरवॉल, Unifi स्विच या अन्य स्रोतों के लॉग को एक टाइमलाइन में लाना आसान है, साथ ही सर्वर और नेटवर्क मेट्रिक्स भी।


## डायग्नोस्टिक एंटिटी

लॉग गतिविधि और लॉग संदेश उत्पन्न करने या उन्हें दूरस्थ सर्वर पर पोस्ट करने में होने वाली त्रुटियों की निगरानी के लिए Home Assistant सेंसर बनाए और अपडेट किए जाते हैं।

![डायग्नोस्टिक एंटिटी](https://remote-logger.rhizomatics.org.uk/assets/images/diagnostic_entities.png){width=480}

##  Home Assistant के लिए Rhizomatics ओपन सोर्स

### HACS
- [AutoArm](https://autoarm.rhizomatics.org.uk) - भौतिक बटन, उपस्थिति, कैलेंडर, सूर्य और अधिक का उपयोग करके Home Assistant अलार्म कंट्रोल पैनल को स्वचालित रूप से आर्म और डिसआर्म करें
- [Supernotify](https://supernotify.rhizomatics.org.uk) - शक्तिशाली चाइम और सुरक्षा कैमरा इंटीग्रेशन सहित आसान मल्टी-चैनल मैसेजिंग के लिए एकीकृत नोटिफिकेशन।


### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - फ़ाइल सिस्टम (NAS/FTP) से MQTT तक वैकल्पिक इमेज विश्लेषण और UK DVLA इंटीग्रेशन के साथ ANPR/ALPR लाइसेंस प्लेट कैमरे इंटीग्रेट करें।
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Docker इमेज अपडेट पर MQTT के माध्यम से स्वचालित रूप से सूचित करें, इमेज से संस्करण और रिलीज़ नोट निकालने की उन्नत हैंडलिंग के साथ, और Home Assistant से कंटेनर को दूरस्थ रूप से पुल और रीस्टार्ट करने का विकल्प। [PyPI](https://pypi.org/project/updates2mqtt/) पर भी उपलब्ध।

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
