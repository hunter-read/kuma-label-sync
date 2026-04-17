# Uptime Kuma Label Sync

A Docker sidecar service that automatically creates, updates, and removes
[Uptime Kuma](https://github.com/louislam/uptime-kuma) monitors based on
Docker container labels. When a container starts with the appropriate labels,
a monitor is created. When it stops, the monitor is removed.

## Features

- **Automatic discovery** — scans running containers for labels
- **Event-driven** — listens for Docker start/stop events in real time
- **Periodic sync** — full reconciliation on a configurable interval
- **Multiple monitors per container** — define any number of monitors on one service
- **Grouping** — automatically creates monitor groups
- **Tagging** — attach arbitrary tags to monitors
- **Notifications** — link existing notification channels by ID
- **Safe** — only manages monitors it created (tracked via a special tag)

## Quick Start

### 1. Docker Compose

```yaml
services:
  uptime-kuma:
    image: louislam/uptime-kuma:1
    container_name: uptime-kuma
    volumes:
      - kuma-data:/app/data
    ports:
      - "3001:3001"
    restart: unless-stopped

  label-sync:
    image: hunterreadca/kuma-label-sync
    container_name: kuma-label-sync
    restart: unless-stopped
    depends_on:
      - uptime-kuma
    environment:
      KUMA_URL: "http://uptime-kuma:3001"
      KUMA_USERNAME: "admin"
      KUMA_PASSWORD: "changeme"
      SYNC_INTERVAL: "30"
      LABEL_PREFIX: "kuma"
      LOG_LEVEL: "INFO"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro

volumes:
  kuma-data:
```

### 2. Label a Container

```yaml
services:
  my-app:
    image: nginx:latest
    labels:
      kuma.enable: "true"
      kuma.name: "My App"
      kuma.type: "http"
      kuma.url: "http://my-app:80"
```

That's it. The monitor appears in Uptime Kuma automatically.

### 3. Multiple Monitors on One Container

Add a monitor name between the prefix and the field to attach multiple monitors to a single container:

```yaml
services:
  my-app:
    image: myapp:latest
    labels:
      # HTTP availability check
      kuma.http.enable: "true"
      kuma.http.name: "My App (HTTP)"
      kuma.http.type: "http"
      kuma.http.url: "http://my-app:8080/health"

      # Docker container status check
      kuma.docker.enable: "true"
      kuma.docker.name: "My App (Container)"
      kuma.docker.type: "docker"
      kuma.docker.docker_host: "1"
      kuma.docker.docker_container: "my-app"
```

Each `<monitor_name>` block is independent — it can have its own type, group, tags, interval, and all other fields. The monitor name is arbitrary; use anything descriptive (`http`, `docker`, `tcp`, `heartbeat`, etc.).

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `KUMA_URL` | `http://uptime-kuma:3001` | Uptime Kuma base URL |
| `KUMA_USERNAME` | _(required)_ | Uptime Kuma login username |
| `KUMA_PASSWORD` | _(required)_ | Uptime Kuma login password |
| `SYNC_INTERVAL` | `30` | Seconds between full sync cycles |
| `LABEL_PREFIX` | `kuma` | Prefix for Docker labels |
| `MANAGED_TAG` | `managed-by-label-sync` | Tag name used to track managed monitors |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `DOCKER_SOCKET` | `unix:///var/run/docker.sock` | Docker socket path |

## Label Reference

All labels use the prefix `kuma.` (configurable via `LABEL_PREFIX`).

### Common Labels (All Monitor Types)

| Label | Required | Default | Description |
| --- | --- | --- | --- |
| `kuma.enable` | **Yes** | — | Set to `true` to enable monitoring |
| `kuma.name` | No | Container name | Display name in Uptime Kuma |
| `kuma.type` | No | `http` | Monitor type (see types below) |
| `kuma.interval` | No | `60` | Check interval in seconds |
| `kuma.retryInterval` | No | `60` | Retry interval in seconds |
| `kuma.maxretries` | No | `0` | Number of retries before marking down |
| `kuma.timeout` | No | `48` | Timeout in seconds |
| `kuma.upsideDown` | No | `false` | Invert monitor (down = up) |
| `kuma.description` | No | — | Monitor description |
| `kuma.group` | No | — | Group name (created automatically) |
| `kuma.tags` | No | — | Comma-separated tags (`key:value,key2:value2`) |
| `kuma.notification_ids` | No | — | Comma-separated notification IDs (`1,2,3`) |

---

## Monitor Types

### HTTP / HTTPS

Checks a URL and expects a successful HTTP response.

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "Web App"
  kuma.type: "http"
  kuma.url: "https://example.com/health"
  kuma.method: "GET"
  kuma.interval: "60"
  kuma.timeout: "30"
  kuma.maxretries: "3"
  kuma.accepted_statuscodes: '["200-299"]'
  kuma.ignoreTls: "false"
  kuma.maxredirects: "10"
  kuma.headers: '{"Authorization": "Bearer token123"}'
  kuma.body: ""
```

| Label | Default | Description |
| --- | --- | --- |
| `kuma.url` | _(required)_ | URL to monitor |
| `kuma.method` | `GET` | HTTP method (`GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `HEAD`, `OPTIONS`) |
| `kuma.headers` | `{}` | JSON string of custom headers |
| `kuma.body` | — | Request body (for POST/PUT) |
| `kuma.accepted_statuscodes` | `["200-299"]` | JSON array of accepted status code ranges |
| `kuma.ignoreTls` | `false` | Ignore TLS certificate errors |
| `kuma.maxredirects` | `10` | Maximum number of redirects to follow |
| `kuma.expectedStatus` | — | Specific expected HTTP status code |
| `kuma.authMethod` | — | Auth method (`basic`, `ntlm`, `mtls`) |
| `kuma.basic_auth_user` | — | Basic auth username |
| `kuma.basic_auth_pass` | — | Basic auth password |
| `kuma.authDomain` | — | NTLM auth domain |
| `kuma.authWorkstation` | — | NTLM auth workstation |

---

### Keyword

Same as HTTP but also checks the response body for a keyword.

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "API Health"
  kuma.type: "keyword"
  kuma.url: "http://api:3000/health"
  kuma.keyword: "healthy"
  kuma.method: "GET"
  kuma.interval: "30"
```

| Label | Default | Description |
| --- | --- | --- |
| `kuma.url` | _(required)_ | URL to check |
| `kuma.keyword` | _(required)_ | Keyword to search for in response body |

All HTTP labels above also apply to keyword monitors.

---

### JSON Query

Checks a JSON API response using a JSONPath expression.

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "API Status Field"
  kuma.type: "json-query"
  kuma.url: "http://api:3000/status"
  kuma.method: "GET"
  kuma.keyword: "ok"
  kuma.interval: "30"
```

| Label | Default | Description |
| --- | --- | --- |
| `kuma.url` | _(required)_ | URL returning JSON |
| `kuma.keyword` | _(required)_ | Expected value from the JSON query |

All HTTP labels also apply.

---

### TCP / Port

Checks if a TCP port is open and accepting connections.

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "PostgreSQL"
  kuma.type: "tcp"
  kuma.hostname: "postgres"
  kuma.port: "5432"
  kuma.interval: "30"
```

| Label | Default | Description |
| --- | --- | --- |
| `kuma.hostname` | _(required)_ | Hostname or IP to connect to |
| `kuma.port` | _(required)_ | TCP port number |

---

### Ping (ICMP)

Sends ICMP ping packets to check if a host is reachable.

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "Gateway"
  kuma.type: "ping"
  kuma.hostname: "192.168.1.1"
  kuma.interval: "60"
```

| Label | Default | Description |
| --- | --- | --- |
| `kuma.hostname` | _(required)_ | Hostname or IP to ping |

> **Note:** The Uptime Kuma container needs `NET_RAW` capability or
> must run as root for ICMP ping to work.

---

### DNS

Resolves a DNS record and optionally checks the result.

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "DNS Check"
  kuma.type: "dns"
  kuma.hostname: "example.com"
  kuma.dns_resolve_type: "A"
  kuma.dns_resolve_server: "1.1.1.1"
  kuma.port: "53"
  kuma.interval: "120"
```

| Label | Default | Description |
| --- | --- | --- |
| `kuma.hostname` | _(required)_ | Domain name to resolve |
| `kuma.dns_resolve_type` | `A` | Record type (`A`, `AAAA`, `CNAME`, `MX`, `NS`, `SOA`, `SRV`, `TXT`, `CAA`) |
| `kuma.dns_resolve_server` | `1.1.1.1` | DNS server to query |
| `kuma.port` | `53` | DNS server port |

---

### Docker

Monitors whether a Docker container is running. Requires a Docker Host
configured in Uptime Kuma settings (Settings → Docker Hosts).

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "Nginx Container"
  kuma.type: "docker"
  kuma.docker_host: "1"
  kuma.docker_container: "nginx-proxy"
  kuma.interval: "30"
```

| Label | Default | Description |
| --- | --- | --- |
| `kuma.docker_host` | _(required)_ | Docker Host ID from Uptime Kuma settings |
| `kuma.docker_container` | _(required)_ | Container name to monitor |

> **Tip:** Find Docker Host IDs in Uptime Kuma under Settings → Docker Hosts.

---

### Steam Game Server

Monitors a Steam game server using the Steam query protocol.

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "Minecraft Server"
  kuma.type: "steam"
  kuma.hostname: "game-server"
  kuma.port: "27015"
  kuma.interval: "60"
```

| Label | Default | Description |
| --- | --- | --- |
| `kuma.hostname` | _(required)_ | Game server hostname or IP |
| `kuma.port` | _(required)_ | Game server query port |

---

### MQTT

Connects to an MQTT broker and subscribes to a topic.

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "MQTT Broker"
  kuma.type: "mqtt"
  kuma.hostname: "mqtt-broker"
  kuma.port: "1883"
  kuma.mqttTopic: "health/check"
  kuma.mqttSuccessMessage: "ok"
  kuma.mqttUsername: "user"
  kuma.mqttPassword: "pass"
  kuma.interval: "60"
```

| Label | Default | Description |
| --- | --- | --- |
| `kuma.hostname` | _(required)_ | MQTT broker hostname |
| `kuma.port` | `1883` | MQTT broker port |
| `kuma.mqttTopic` | _(required)_ | Topic to subscribe to |
| `kuma.mqttSuccessMessage` | — | Expected message (blank = any message) |
| `kuma.mqttUsername` | — | MQTT username |
| `kuma.mqttPassword` | — | MQTT password |

---

### gRPC Keyword

Sends a gRPC request and checks the response for a keyword.

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "gRPC Service"
  kuma.type: "grpc-keyword"
  kuma.grpcUrl: "grpc-service:50051"
  kuma.grpcServiceName: "health"
  kuma.grpcMethod: "Check"
  kuma.keyword: "SERVING"
  kuma.grpcEnableTls: "false"
  kuma.interval: "30"
```

| Label | Default | Description |
| --- | --- | --- |
| `kuma.grpcUrl` | _(required)_ | gRPC server `host:port` |
| `kuma.grpcServiceName` | — | gRPC service name |
| `kuma.grpcMethod` | — | gRPC method name |
| `kuma.keyword` | _(required)_ | Expected keyword in response |
| `kuma.grpcBody` | — | gRPC request body (JSON) |
| `kuma.grpcMetadata` | — | gRPC metadata (JSON) |
| `kuma.grpcProtobuf` | — | Protobuf definition |
| `kuma.grpcEnableTls` | `false` | Enable TLS for gRPC |

---

### Push

A passive monitor that expects to receive a heartbeat push at a regular
interval. Uptime Kuma generates a unique push URL for this monitor.

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "Cron Job Heartbeat"
  kuma.type: "push"
  kuma.interval: "300"
  kuma.maxretries: "0"
```

No extra labels required. After creation, find the push URL in Uptime Kuma's
UI and configure your cron job / service to POST to it.

---

### SQL Server (MSSQL)

Connects to a Microsoft SQL Server and optionally runs a query.

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "MSSQL Database"
  kuma.type: "sqlserver"
  kuma.databaseConnectionString: "Server=mssql;Database=mydb;User Id=sa;Password=pass;Encrypt=false;"
  kuma.databaseQuery: "SELECT 1"
  kuma.interval: "60"
```

| Label | Default | Description |
| --- | --- | --- |
| `kuma.databaseConnectionString` | _(required)_ | MSSQL connection string |
| `kuma.databaseQuery` | — | Query to execute (success = returns rows) |

---

### PostgreSQL

Connects to a PostgreSQL database and optionally runs a query.

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "Postgres DB"
  kuma.type: "postgres"
  kuma.databaseConnectionString: "postgresql://user:pass@postgres:5432/mydb"
  kuma.databaseQuery: "SELECT 1"
  kuma.interval: "60"
```

| Label | Default | Description |
| --- | --- | --- |
| `kuma.databaseConnectionString` | _(required)_ | PostgreSQL connection URI |
| `kuma.databaseQuery` | — | Query to execute |

---

### MySQL

Connects to a MySQL/MariaDB database and optionally runs a query.

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "MySQL DB"
  kuma.type: "mysql"
  kuma.databaseConnectionString: "mysql://user:pass@mysql:3306/mydb"
  kuma.databaseQuery: "SELECT 1"
  kuma.interval: "60"
```

| Label | Default | Description |
| --- | --- | --- |
| `kuma.databaseConnectionString` | _(required)_ | MySQL connection URI |
| `kuma.databaseQuery` | — | Query to execute |

---

### MongoDB

Connects to a MongoDB instance and runs a ping command.

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "Mongo DB"
  kuma.type: "mongodb"
  kuma.databaseConnectionString: "mongodb://user:pass@mongo:27017/mydb"
  kuma.interval: "60"
```

| Label | Default | Description |
| --- | --- | --- |
| `kuma.databaseConnectionString` | _(required)_ | MongoDB connection URI |

---

### Redis

Connects to a Redis instance.

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "Redis Cache"
  kuma.type: "redis"
  kuma.databaseConnectionString: "redis://redis:6379"
  kuma.interval: "30"
```

| Label | Default | Description |
| --- | --- | --- |
| `kuma.databaseConnectionString` | _(required)_ | Redis connection URI |

---

### RADIUS

Performs a RADIUS authentication check.

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "RADIUS Server"
  kuma.type: "radius"
  kuma.hostname: "radius-server"
  kuma.port: "1812"
  kuma.radiusUsername: "testuser"
  kuma.radiusPassword: "testpass"
  kuma.radiusSecret: "sharedsecret"
  kuma.radiusCalledStationId: "00-00-00-00-00-00"
  kuma.radiusCallingStationId: "00-00-00-00-00-00"
  kuma.interval: "60"
```

| Label | Default | Description |
| --- | --- | --- |
| `kuma.hostname` | _(required)_ | RADIUS server hostname |
| `kuma.port` | `1812` | RADIUS server port |
| `kuma.radiusUsername` | _(required)_ | Test username |
| `kuma.radiusPassword` | _(required)_ | Test password |
| `kuma.radiusSecret` | _(required)_ | RADIUS shared secret |
| `kuma.radiusCalledStationId` | — | Called station ID |
| `kuma.radiusCallingStationId` | — | Calling station ID |

---

### Real Browser

Uses a real Chromium browser to load a page and check for errors.

```yaml
labels:
  kuma.enable: "true"
  kuma.name: "SPA Frontend"
  kuma.type: "real-browser"
  kuma.url: "https://my-spa.example.com"
  kuma.interval: "120"
```

| Label | Default | Description |
| --- | --- | --- |
| `kuma.url` | _(required)_ | URL to load in the browser |

> **Note:** Requires Chromium to be available in the Uptime Kuma container.
> Use the `louislam/uptime-kuma:1` image which includes it, or mount a
> Chromium binary.

---

## Multiple Monitors per Container

By default, labels use a flat structure (`kuma.<field>`) that creates one monitor per container.
To create multiple monitors from a single container, add a monitor name as an extra segment:

```
kuma.<monitor_name>.<field>
```

Each named block is entirely independent and can define its own type, URL, group, tags, interval, etc.

```yaml
services:
  my-app:
    image: myapp:latest
    labels:
      # HTTP health check
      kuma.http.enable: "true"
      kuma.http.name: "My App (HTTP)"
      kuma.http.group: "Application"
      kuma.http.type: "http"
      kuma.http.url: "http://my-app:8080/health"
      kuma.http.interval: "60"
      kuma.http.maxretries: "3"

      # Docker container status
      kuma.docker.enable: "true"
      kuma.docker.name: "My App (Container)"
      kuma.docker.group: "Application"
      kuma.docker.type: "docker"
      kuma.docker.docker_host: "1"
      kuma.docker.docker_container: "my-app"
      kuma.docker.interval: "30"

      # TCP port check
      kuma.tcp.enable: "true"
      kuma.tcp.name: "My App (Port)"
      kuma.tcp.type: "tcp"
      kuma.tcp.hostname: "my-app"
      kuma.tcp.port: "8080"
```

> **Note:** Flat labels (`kuma.<field>`) and named labels (`kuma.<name>.<field>`) cannot be mixed on the same container. Use one scheme or the other.

> **Default name:** If `kuma.<monitor_name>.name` is omitted, the monitor is named `<container_name> (<monitor_name>)` automatically.

---

## Grouping

Use `kuma.group` to organize monitors into groups. Groups are created
automatically if they don't exist.

```yaml
# These two containers will appear under a "Databases" group
services:
  postgres:
    image: postgres:16
    labels:
      kuma.enable: "true"
      kuma.name: "PostgreSQL"
      kuma.type: "tcp"
      kuma.hostname: "postgres"
      kuma.port: "5432"
      kuma.group: "Databases"

  redis:
    image: redis:7
    labels:
      kuma.enable: "true"
      kuma.name: "Redis"
      kuma.type: "tcp"
      kuma.hostname: "redis"
      kuma.port: "6379"
      kuma.group: "Databases"
```

## Tags

Attach tags to monitors using comma-separated `key:value` pairs.

```yaml
labels:
  kuma.tags: "env:production,team:platform,tier:critical"
```

Tags are created in Uptime Kuma automatically if they don't exist.

## Notifications

Link monitors to existing notification channels by their Uptime Kuma IDs.

```yaml
labels:
  kuma.notification_ids: "1,3,5"
```

> Find notification IDs in Uptime Kuma under Settings → Notifications.
> The ID is visible in the URL when editing a notification.

## How It Works

1. **Startup** — connects to Uptime Kuma via Socket.IO, waits until ready,
   then performs a full sync.
2. **Event-driven** — listens on the Docker socket for container
   `start`/`stop`/`die`/`destroy` events and triggers a re-sync with a 2s
   debounce.
3. **Periodic sync** — a full reconciliation runs every `SYNC_INTERVAL`
   seconds as a safety net.
4. **Managed tag** — a special tag (`managed-by-label-sync`) is attached to
   every monitor the service creates. It never touches monitors created
   manually or by other tools.
5. **Cleanup** — when a container stops or its `kuma.enable` label is
   removed, the corresponding monitor is automatically deleted.

## All Supported Labels

| Label | Type | Used By | Description |
| --- | --- | --- | --- |
| `kuma.enable` | `string` | All | `true` to enable |
| `kuma.name` | `string` | All | Monitor display name |
| `kuma.type` | `string` | All | Monitor type |
| `kuma.interval` | `int` | All | Check interval (seconds) |
| `kuma.retryInterval` | `int` | All | Retry interval (seconds) |
| `kuma.maxretries` | `int` | All | Max retries before down |
| `kuma.timeout` | `int` | All | Timeout (seconds) |
| `kuma.upsideDown` | `bool` | All | Invert status |
| `kuma.description` | `string` | All | Description text |
| `kuma.group` | `string` | All | Group name |
| `kuma.tags` | `string` | All | Tags (`key:val,key2:val2`) |
| `kuma.notification_ids` | `string` | All | Notification IDs (`1,2,3`) |
| `kuma.url` | `string` | http, keyword, json-query, real-browser | URL to monitor |
| `kuma.method` | `string` | http, keyword, json-query | HTTP method |
| `kuma.headers` | `string` | http, keyword, json-query | JSON headers |
| `kuma.body` | `string` | http, keyword, json-query | Request body |
| `kuma.accepted_statuscodes` | `json` | http, keyword, json-query | Accepted status codes |
| `kuma.ignoreTls` | `bool` | http, keyword, json-query | Ignore TLS errors |
| `kuma.maxredirects` | `int` | http, keyword, json-query | Max redirects |
| `kuma.expectedStatus` | `int` | http | Expected status code |
| `kuma.authMethod` | `string` | http, keyword | Auth method |
| `kuma.basic_auth_user` | `string` | http, keyword | Basic auth user |
| `kuma.basic_auth_pass` | `string` | http, keyword | Basic auth password |
| `kuma.authDomain` | `string` | http, keyword | NTLM domain |
| `kuma.authWorkstation` | `string` | http, keyword | NTLM workstation |
| `kuma.keyword` | `string` | keyword, json-query, grpc-keyword | Search keyword |
| `kuma.hostname` | `string` | tcp, ping, dns, mqtt, steam, radius | Target hostname |
| `kuma.port` | `int` | tcp, dns, mqtt, steam, radius | Target port |
| `kuma.dns_resolve_type` | `string` | dns | DNS record type |
| `kuma.dns_resolve_server` | `string` | dns | DNS server |
| `kuma.docker_host` | `int` | docker | Docker Host ID |
| `kuma.docker_container` | `string` | docker | Container name |
| `kuma.mqttTopic` | `string` | mqtt | MQTT topic |
| `kuma.mqttUsername` | `string` | mqtt | MQTT username |
| `kuma.mqttPassword` | `string` | mqtt | MQTT password |
| `kuma.mqttSuccessMessage` | `string` | mqtt | Expected MQTT message |
| `kuma.grpcUrl` | `string` | grpc-keyword | gRPC `host:port` |
| `kuma.grpcBody` | `string` | grpc-keyword | gRPC request body |
| `kuma.grpcMetadata` | `string` | grpc-keyword | gRPC metadata |
| `kuma.grpcServiceName` | `string` | grpc-keyword | gRPC service name |
| `kuma.grpcMethod` | `string` | grpc-keyword | gRPC method |
| `kuma.grpcProtobuf` | `string` | grpc-keyword | Protobuf definition |
| `kuma.grpcEnableTls` | `bool` | grpc-keyword | Enable gRPC TLS |
| `kuma.databaseConnectionString` | `string` | sqlserver, postgres, mysql, mongodb, redis | Connection string |
| `kuma.databaseQuery` | `string` | sqlserver, postgres, mysql | SQL query |
| `kuma.radiusUsername` | `string` | radius | RADIUS username |
| `kuma.radiusPassword` | `string` | radius | RADIUS password |
| `kuma.radiusSecret` | `string` | radius | RADIUS shared secret |
| `kuma.radiusCalledStationId` | `string` | radius | Called station ID |
| `kuma.radiusCallingStationId` | `string` | radius | Calling station ID |
| `kuma.proxyId` | `int` | http, keyword, json-query | Proxy ID from Kuma settings |

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE) for details.