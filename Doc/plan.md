# 物联网设备模拟与规则引擎平台 - 实施计划

## 系统架构

```
┌──────────────┐     MQTT      ┌──────────────┐
│   Device     │──────────────▶│  Mosquitto   │
│  Simulator   │               │  (with ACL)  │
│  (10k devs)  │               └──────┬───────┘
└──────────────┘                      │
                                      │ Subscribe: edgefleet/+/+/+/telemetry
                                      ▼
                              ┌────────────────┐
                              │  Ingestion     │
                              │  Service       │
                              └───┬─────┬──────┘
                                  │     │
                    ┌─────────────┘     └─────────────┐
                    ▼                                   ▼
            ┌──────────────┐                  ┌──────────────┐
            │  InfluxDB    │                  │  Rule Engine │
            │  (存储)       │                  │  (内存状态机)  │
            └──────────────┘                  └──────┬───────┘
                    ▲                                  │
                    │                                  ▼
            ┌──────────────┐                  ┌──────────────┐
            │  FastAPI     │◀────────────────▶│  Alarm Mgr   │──▶ Webhook
            │  (REST API)  │                  └──────────────┘
            └──────┬───────┘
                   │
         ┌─────────┴──────────┐
         ▼                     ▼
┌──────────────┐      ┌──────────────┐
│  WebSocket   │◀─────│   Redis      │
│  Server      │      │  (Pub/Sub)   │
└──────┬───────┘      └──────────────┘
       ▼
┌──────────────┐
│  React +     │
│  ECharts     │
└──────────────┘
```

## 规则引擎延迟分析 (500并发告警)

| 指标 | 值 |
|------|-----|
| 单消息评估延迟 | ~0.2ms |
| 吞吐量(单worker) | ~5,000 eval/s |
| 2000设备×50规则 | 10,000 eval/s (需2-4 worker) |
| p50 端到端(发布→告警触发) | 5ms |
| p95 端到端(发布→Webhook送达) | 150ms |
| 内存占用(10k设备×5规则) | ~25MB |

## 核心模块

- **虚拟设备模拟器** (`simulator/`): 批量生成温湿度传感器，随机游走模型，支持异常注入
- **MQTT消息网关** (`backend/app/services/mqtt_ingestion.py`): 接入设备消息，去重，转发到存储与规则引擎
- **时序数据存储** (`backend/app/services/influx_writer.py`): InfluxDB批量写入，按org_id tag隔离
- **规则引擎** (`backend/app/rule_dsl/` + `backend/app/services/rule_engine.py`): JSON DSL解析→AST→递归求值→状态机转换
- **告警管理** (`backend/app/services/alarm_manager.py`): 触发/恢复状态管理，Webhook分发
- **实时仪表盘** (`frontend/`): React + ECharts + WebSocket实时推送
- **多租户权限** (`backend/app/middleware/tenant_context.py`): JWT + 中间件 + 查询级过滤

## 关键技术决策

1. **纯内存状态机**: 每个(device_id, rule_id)维护ring buffer(deque, maxlen=100) + NORMAL/ALARM状态
2. **批量写InfluxDB**: 500点或1秒flush，不逐条写入
3. **Redis Pub/Sub**: 解耦规则引擎与WebSocket推送，支持多实例
4. **Mosquitto ACL pattern**: `readwrite edgefleet/%u/#` 实现broker层租户隔离
5. **JWT claims**: `org_id, group_ids[], role` 注入每个请求，查询级数据过滤

## 验证方式

```bash
# 一键启动
docker-compose -f deploy/docker-compose.yml up -d

# 2000设备压测
docker-compose -f deploy/docker-compose.yml --profile testing up simulator

# 运行测试
pytest tests/ -v

# 访问仪表盘
http://localhost:3000
```

## 规范文档

- `docs/mqtt_topic_spec.md` - MQTT主题格式与负载结构
- `docs/alarm_rule_dsl_spec.md` - 告警规则DSL语法与求值语义
- `docs/permission_model_spec.md` - 三级权限模型与隔离策略
