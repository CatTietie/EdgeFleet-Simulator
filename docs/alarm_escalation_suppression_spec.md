# 告警升级链与关联抑制机制需求规格

## 背景与目标
EdgeFleet-Simulator当前的告警管理器在规则触发后仅通过Redis Pub/Sub广播事件，没有升级机制和抑制机制。当设备持续异常时，同一条规则反复触发，产生大量重复告警事件，前端WebSocket连接被同一告警刷屏。不同规则之间没有关联抑制，温度超限和湿度超限可能由同一个设备故障引起，运维收到两条独立告警无法快速判断关联性。

需要实现告警升级链和关联抑制：告警持续超阈值时按升级链逐级提升严重度，短时间重复触发自动抑制，关联设备的告警聚合展示。

## 需求清单
- R-AE-01: 告警升级链：每条规则可配多级阈值（如WARNING→CRITICAL→EMERGENCY），各级别对应不同通知策略
- R-AE-02: 升级判定：同一规则对同一设备持续触发，每次检查严重度高于上次则升级，低于则不降级
- R-AE-03: 告警抑制：同一规则+同一设备在抑制窗口内重复触发，只更新计数和最新时间戳，不生成新事件
- R-AE-04: 关联抑制：同一组织下同一设备在短时间内触发多条不同规则，自动聚合为关联告警组
- R-AE-05: 告警恢复：设备指标回归正常后自动清除活跃告警，通过WebSocket推送恢复事件
- R-AE-06: 告警事件模型扩展：escalation_level, suppressed_count, correlation_group_id, recovered_at
- R-AE-07: 前端告警面板显示升级标识、关联聚合和恢复状态
- R-AE-08: Webhook分发时携带升级级别和关联组信息

## 现有架构约束
- 告警管理器使用Redis Pub/Sub广播，WebSocket管理器扇出到前端
- 规则引擎求值后回调告警管理器，告警事件存内存列表
- 告警规则DSL支持CompareExpr和LogicalExpr，但无升级阈值配置
- 多租户通过JWT中间件过滤组织，告警关联需在同一组织范围内

## 技术栈约束
- 后端：FastAPI + PostgreSQL + InfluxDB + Redis
- 告警规则：自定义DSL + AST递归求值
- 通知：Redis Pub/Sub → WebSocket + Webhook
- 前端：React + D3.js

## 数据模型变更
- AlarmRule新增：escalation_levels (JSONB), suppress_window_seconds (INT)
- AlarmEvent新增：escalation_level (TEXT), suppressed_count (INT), correlation_group_id (UUID), recovered_at (TIMESTAMP)
- 新增 CorrelationGroup 模型：group_id, organization_id, device_id, rule_ids, started_at, ended_at
- 新增 EventType：ALARM_ESCALATED / ALARM_SUPPRESSED / ALARM_RECOVERED / ALARMS_CORRELATED

## 流程设计
1. 规则触发 → 查找活跃告警 → 存在则在抑制窗口内合并计数
2. 不在抑制窗口 → 新建告警事件 → 推送通知
3. 持续触发 → 检查升级阈值 → 超过则升级 → 推送升级通知
4. 同设备多规则触发 → 创建/追加关联组 → 聚合展示
5. 指标回归正常 → 标记恢复 → 推送恢复事件

## 边界条件与异常处理
- 升级后指标恢复又恶化：重新从WARNING开始升级
- 关联组内部分告警恢复：组保留，标记部分恢复
- 抑制窗口与升级周期冲突：先判断升级再判断抑制
- Redis断连时抑制状态丢失：从数据库重建活跃告警列表

## 验收标准
- 同一设备同规则30秒内重复触发只生成1条告警，suppressed_count累加
- 持续恶化3个周期后告警从WARNING升级到CRITICAL，前端显示升级标识
- 同设备5秒内触发2条不同规则，前端聚合为关联告警组
- 设备恢复正常后活跃告警自动标记恢复并推送恢复事件
