These are working examples, not ideal recommendations.

The Vector config will also pull in Docker logs and systemd journal from the box on which it runs ( excluding Vector and OpenObserve from the Docker logging to prevent cycles).

OpenObserve handles OTLP directly, so Vector can be skipped if there's no syslog to capture, and no Docker ( or a native OTLP collector installed for Docker)
