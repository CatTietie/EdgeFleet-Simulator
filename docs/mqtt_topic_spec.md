# MQTT Topic Format Specification

## Topic Hierarchy

```
edgefleet/{org_id}/{group_id}/{device_id}/{channel}
```

| Segment | Description | Constraints |
|---------|-------------|-------------|
| `edgefleet` | Fixed namespace prefix | Literal string |
| `org_id` | Organization identifier | `[a-z0-9-]+`, max 36 chars |
| `group_id` | Device group within org | `[a-z0-9-]+`, max 36 chars |
| `device_id` | Unique device identifier | `[a-z0-9-]+`, max 64 chars |
| `channel` | Message type | One of: `telemetry`, `status`, `command`, `alarm` |

## Channels

| Channel | Direction | QoS | Retained | Purpose |
|---------|-----------|-----|----------|---------|
| `telemetry` | Device → Platform | 0 | No | Periodic sensor readings |
| `status` | Device → Platform | 1 | Yes | Online/offline heartbeat |
| `command` | Platform → Device | 1 | No | Control commands |
| `alarm` | Platform internal | 1 | No | Alarm event fan-out |

## Payload Schemas

### Telemetry (`telemetry` channel)

```json
{
  "device_id": "sensor-0042",
  "timestamp": 1717849200000,
  "metrics": {
    "temperature": 78.5,
    "humidity": 45.2
  },
  "seq": 12345
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `device_id` | string | Yes | Must match topic segment |
| `timestamp` | integer | Yes | Unix epoch milliseconds |
| `metrics` | object | Yes | Key-value pairs of metric name to numeric value |
| `seq` | integer | Yes | Monotonically increasing sequence number per device |

### Status (`status` channel)

```json
{
  "device_id": "sensor-0042",
  "timestamp": 1717849200000,
  "status": "online",
  "uptime_seconds": 86400,
  "firmware_version": "1.2.3"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `device_id` | string | Yes | Must match topic segment |
| `timestamp` | integer | Yes | Unix epoch milliseconds |
| `status` | string | Yes | `online` or `offline` |
| `uptime_seconds` | integer | No | Seconds since boot |
| `firmware_version` | string | No | Semantic version |

### Command (`command` channel)

```json
{
  "command_id": "cmd-uuid-001",
  "type": "set_interval",
  "params": {
    "interval_seconds": 10
  },
  "issued_at": 1717849200000,
  "issued_by": "user-uuid-001"
}
```

### Alarm (`alarm` channel)

```json
{
  "alarm_id": "alm-uuid-001",
  "rule_id": "rule-001",
  "device_id": "sensor-0042",
  "event_type": "triggered",
  "severity": "critical",
  "values": {
    "temperature": 85.2,
    "humidity": 18.1
  },
  "triggered_at": 1717849200000,
  "message": "High Temp Low Humidity Alert triggered"
}
```

## ACL and Authentication

### Authentication
- Each organization is assigned an MQTT username equal to its `org_id`
- The platform ingestion service uses a dedicated `platform-service` account
- Authentication via username/password (dev) or TLS client certificates (production)

### ACL Rules

```
# Platform service: read all, write commands/alarms
user platform-service
topic read edgefleet/#
topic write edgefleet/+/+/+/command
topic write edgefleet/+/+/+/alarm

# Per-org devices: read/write only under own org prefix
pattern readwrite edgefleet/%u/#
```

### Subscription Patterns

| Consumer | Subscription | Purpose |
|----------|-------------|---------|
| Ingestion Service | `edgefleet/+/+/+/telemetry` | All telemetry from all orgs |
| Ingestion Service | `edgefleet/+/+/+/status` | All device status updates |
| Per-org WS fan-out | `edgefleet/{org_id}/+/+/alarm` | Alarm events for specific org |

## Message Guarantees

- Telemetry: QoS 0 (at most once). Acceptable loss under heavy load.
- Status: QoS 1 (at least once) + Retained. Last known status always available.
- Command: QoS 1 (at least once). Commands must not be silently dropped.
- Deduplication: Platform deduplicates by `(device_id, seq)` within a 60-second window.
