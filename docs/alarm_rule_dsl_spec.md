# Alarm Rule DSL Specification

## Overview

The alarm rule DSL defines conditions under which the platform triggers or recovers alarms. Rules are stored as JSON documents and evaluated in real-time as telemetry arrives.

## Rule Structure

```json
{
  "rule_id": "string (UUID)",
  "name": "string",
  "description": "string",
  "org_id": "string",
  "enabled": true,
  "target": { ... },
  "trigger_condition": { ... },
  "recovery_condition": { ... },
  "severity": "critical | warning | info",
  "actions": { ... },
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

## Target Specification

Defines which devices this rule applies to.

```json
{
  "scope": "org | group | device",
  "group_id": "string | null",
  "device_ids": ["string"] | null
}
```

| Scope | Behavior |
|-------|----------|
| `org` | Rule applies to all devices in the organization |
| `group` | Rule applies to all devices in the specified `group_id` |
| `device` | Rule applies only to devices listed in `device_ids` |

## Condition Grammar

```
Condition    := LogicalExpr | CompareExpr
LogicalExpr  := { "operator": "AND" | "OR", "conditions": Condition[] }
CompareExpr  := { "metric": string, "comparator": Comparator, "threshold": number, "temporal": Temporal | null }
Comparator   := ">" | "<" | ">=" | "<=" | "==" | "!="
Temporal     := ConsecutiveTemporal | WindowTemporal
ConsecutiveTemporal := { "type": "consecutive", "count": integer }
WindowTemporal      := { "type": "within", "seconds": integer, "min_occurrences": integer }
```

## Condition Types

### CompareExpr (Leaf Condition)

```json
{
  "metric": "temperature",
  "comparator": ">",
  "threshold": 80,
  "temporal": {
    "type": "consecutive",
    "count": 3
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `metric` | string | Yes | Name of the metric to evaluate (must match a key in telemetry `metrics`) |
| `comparator` | string | Yes | One of: `>`, `<`, `>=`, `<=`, `==`, `!=` |
| `threshold` | number | Yes | Numeric threshold value |
| `temporal` | object/null | No | Temporal constraint; null means evaluate against latest single reading |

### LogicalExpr (Combinator)

```json
{
  "operator": "AND",
  "conditions": [
    { "metric": "temperature", "comparator": ">", "threshold": 80, "temporal": { "type": "consecutive", "count": 3 } },
    { "metric": "humidity", "comparator": "<", "threshold": 20, "temporal": null }
  ]
}
```

Nesting is allowed up to 3 levels deep.

## Temporal Semantics

### No Temporal Constraint (`temporal: null`)

Evaluates against the **latest single reading** of the specified metric.

### Consecutive (`type: "consecutive"`)

Maintains a ring buffer of the last `count` readings for the metric per device.
The condition is **true** only when **all** of the most recent `count` readings satisfy the comparator.

If fewer than `count` readings have been received, the condition is **false**.

### Within (`type: "within"`)

Maintains a time-windowed buffer of readings within the last `seconds` seconds.
The condition is **true** when at least `min_occurrences` readings within the window satisfy the comparator.

## Evaluation Semantics

1. When a telemetry message arrives, the rule engine identifies all applicable rules for that device (by org, group, device target matching).
2. For each applicable rule, the engine updates the ring buffers with the new data point.
3. Based on the **current alarm state** of the (device, rule) pair:
   - If **NORMAL**: evaluate `trigger_condition`. If true → transition to **ALARM**.
   - If **ALARM**: evaluate `recovery_condition`. If true → transition to **NORMAL**.
4. On state transition, emit an alarm event and execute actions.

## State Machine

```
         trigger_condition == true
NORMAL ──────────────────────────────▶ ALARM
   ▲                                      │
   │    recovery_condition == true         │
   └──────────────────────────────────────┘
```

### State Transition Rules

- **NORMAL → ALARM**: `trigger_condition` evaluates to true. Cooldown timer starts.
- **ALARM → NORMAL**: `recovery_condition` evaluates to true. (If no `recovery_condition` is defined, alarm remains until the `trigger_condition` becomes false for 5 consecutive readings.)
- **Cooldown**: After a trigger, the same (device, rule) pair cannot re-trigger for `cooldown_seconds`.
- **Initial state**: All (device, rule) pairs start in NORMAL.

## Recovery Condition

Optional. If omitted, default recovery behavior is:
- The trigger condition must be **false** for 5 consecutive evaluations.

If specified, the recovery condition uses the same grammar as the trigger condition but defines explicit "back to normal" criteria (e.g., temperature drops below 75 for 2 consecutive readings).

## Actions

```json
{
  "webhook_urls": ["https://hooks.example.com/alert", "https://backup.example.com/alert"],
  "cooldown_seconds": 60
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `webhook_urls` | string[] | Yes | HTTP endpoints to POST alarm events to |
| `cooldown_seconds` | integer | Yes | Minimum seconds between repeated triggers for same (device, rule) |

## Webhook Payload

Sent as HTTP POST with `Content-Type: application/json`:

```json
{
  "alarm_id": "alm-uuid-001",
  "rule_id": "rule-001",
  "rule_name": "High Temp Low Humidity Alert",
  "device_id": "sensor-0042",
  "org_id": "org-abc123",
  "group_id": "floor-3",
  "event_type": "triggered | recovered",
  "severity": "critical | warning | info",
  "values": {
    "temperature": 85.2,
    "humidity": 18.1
  },
  "message": "High Temp Low Humidity Alert triggered on sensor-0042",
  "triggered_at": "2026-06-08T10:30:00Z",
  "recovered_at": null
}
```

## Complete Example

"Temperature exceeds 80 for 3 consecutive readings AND humidity below 20":

```json
{
  "rule_id": "rule-001",
  "name": "High Temp Low Humidity Alert",
  "description": "Triggers when temperature is critically high and humidity dangerously low",
  "org_id": "org-abc123",
  "enabled": true,
  "target": {
    "scope": "group",
    "group_id": "floor-3",
    "device_ids": null
  },
  "trigger_condition": {
    "operator": "AND",
    "conditions": [
      {
        "metric": "temperature",
        "comparator": ">",
        "threshold": 80,
        "temporal": {
          "type": "consecutive",
          "count": 3
        }
      },
      {
        "metric": "humidity",
        "comparator": "<",
        "threshold": 20,
        "temporal": null
      }
    ]
  },
  "recovery_condition": {
    "operator": "AND",
    "conditions": [
      {
        "metric": "temperature",
        "comparator": "<=",
        "threshold": 75,
        "temporal": {
          "type": "consecutive",
          "count": 2
        }
      }
    ]
  },
  "severity": "critical",
  "actions": {
    "webhook_urls": ["https://hooks.example.com/alert"],
    "cooldown_seconds": 60
  }
}
```

## Boundary Conditions

| Scenario | Expected Behavior |
|----------|-------------------|
| Value exactly equals threshold with `>` | Does **NOT** trigger |
| Value exactly equals threshold with `>=` | **DOES** trigger |
| Consecutive count at N-1 readings | Does **NOT** trigger |
| Nth consecutive reading satisfies comparator | **DOES** trigger |
| Device offline, ring buffer incomplete | Condition is **false** (insufficient data) |
| Ring buffer stale (no reading for >60s) | Buffer cleared, count resets |
