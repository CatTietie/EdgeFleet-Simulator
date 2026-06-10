# 规则引擎分布式状态持久化与热重载需求规格

## 背景与目标
EdgeFleet-Simulator当前的规则状态机使用纯内存字典存储设备规则状态（StateStore），进程重启后所有状态丢失。规则变更需要重启服务才能生效，没有热重载机制。在多实例部署场景下，不同实例的状态不一致，同一设备在不同实例上可能处于不同状态。

需要实现规则状态持久化和热重载：状态存储在Redis中支持多实例共享，规则变更后自动热重载无需重启，状态机支持从Redis恢复。

## 需求清单
- R-RH-01: 规则状态从内存字典迁移到Redis Hash，按organization:device:rule_id存储
- R-RH-02: 状态机每次转换后同步写入Redis，保证持久化
- R-RH-03: 进程启动时从Redis加载已有状态，恢复状态机到上次状态
- R-RH-04: 规则变更（增删改）后自动触发热重载，无需重启服务
- R-RH-05: 热重载过程中正在求值的规则继续用旧版本完成，新请求使用新版本
- R-RH-06: 规则版本管理：每次变更生成新版本号，状态记录关联版本
- R-RH-07: 多实例部署时通过Redis Pub/Sub通知其他实例重载规则
- R-RH-08: 热重载事件通过WebSocket推送到前端

## 现有架构约束
- StateStore是纯内存dict，DeviceRuleState仅含status和ring buffer
- 规则引擎在lifespan中从PostgreSQL加载规则到内存，运行期间不刷新
- 状态机支持NORMAL/ALARM二态，ring buffer存储最近100个求值结果
- Redis已用于Pub/Sub和缓存，基础设施可用

## 技术栈约束
- 后端：FastAPI + PostgreSQL + InfluxDB + Redis
- 规则引擎：自定义DSL + AST递归求值 + 状态机
- 状态存储：Redis Hash + JSON序列化
- 通知：Redis Pub/Sub

## 数据模型变更
- AlarmRule新增：version (INT), updated_at (TIMESTAMP)
- DeviceRuleState新增：rule_version (INT), last_transition_at (TIMESTAMP)
- Redis Key设计：rule_state:{org_id}:{device_id}:{rule_id} → JSON
- 新增 Redis Channel：rule_reload 通知其他实例
- 新增 EventType：RULE_RELOADED / STATE_RECOVERED

## 流程设计
1. 状态持久化：状态转换 → 序列化为JSON → 写入Redis Hash → 确认写入
2. 状态恢复：启动时扫描Redis rule_state:* → 反序列化 → 重建StateStore
3. 热重载：规则变更 → 递增版本号 → 发布rule_reload消息 → 各实例加载新规则
4. 版本隔离：正在执行的求值锁定当前版本，新请求使用新版本
5. Ring buffer持久化：每次追加后更新Redis，恢复时重建buffer

## 边界条件与异常处理
- Redis不可用时降级为内存存储，标记为降级模式
- 状态恢复时规则已删除：忽略该状态记录
- 热重载时状态机正在ALARM状态：保留当前状态，新规则版本从下次求值生效
- 多实例同时写同一设备状态：Redis原子操作保证一致性
- Ring buffer超过100条：持久化时只保留最新100条

## 验收标准
- 进程重启后设备规则状态与重启前一致
- 修改告警规则阈值后无需重启，新阈值在下次求值时生效
- 热重载期间正在执行的求值使用旧规则版本完成
- 多实例部署时修改规则后所有实例在5秒内加载新规则
- Redis不可用时系统降级为内存模式并记录警告
