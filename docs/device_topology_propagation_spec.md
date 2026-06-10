# 设备依赖拓扑与故障传播引擎需求规格

## 背景与目标
EdgeFleet-Simulator当前设备之间是扁平关系，没有依赖拓扑。当网关设备宕机时，其下所有传感器设备的告警其实是同一个根因——网关故障，但系统把每个传感器的超时告警都独立触发，运维看到一屏告警却不知道先修哪个。没有故障传播链，无法从叶子告警追溯到根因设备。

需要实现设备依赖拓扑和故障传播引擎：定义设备间依赖关系，故障发生时沿依赖链反向传播，自动标注根因设备和受影响设备，抑制受影响设备的衍生告警。

## 需求清单
- R-DT-01: 支持定义设备依赖关系：网关→传感器、主控→从节点等父子拓扑
- R-DT-02: 依赖关系存储在PostgreSQL，支持API增删改查
- R-DT-03: 故障传播引擎：设备宕机时沿依赖链标记所有下游设备为受影响状态
- R-DT-04: 受影响设备的告警自动标注为衍生告警，与根因告警关联
- R-DT-05: 衍生告警默认抑制通知，仅在根因告警详情中展示
- R-DT-06: 根因恢复后自动清除所有下游设备的受影响标记
- R-DT-07: 前端拓扑图展示依赖连线，根因设备红色脉冲，受影响设备橙色，正常设备绿色
- R-DT-08: 拓扑图支持拖拽编辑依赖关系

## 现有架构约束
- 设备模型在PostgreSQL，当前无依赖关系字段
- 拓扑图使用D3力导向图，当前只展示设备状态无连线
- 告警规则引擎对每个设备独立求值，需增加传播上下文
- 多租户组织隔离，依赖关系仅在同一组织内生效

## 技术栈约束
- 后端：FastAPI + PostgreSQL + InfluxDB + Redis
- 前端：React + D3.js
- 设备模型：SQLAlchemy
- 事件通道：Redis Pub/Sub → WebSocket

## 数据模型变更
- 新表 device_dependencies：id, parent_device_id, child_device_id, dependency_type, organization_id
- Device模型新增：dependency_parent_id (FK), is_affected (BOOL), affected_by_device_id (FK)
- AlarmEvent新增：is_derived (BOOL), root_cause_device_id (FK), root_cause_alarm_id (FK)
- 新增API：CRUD /api/v1/devices/dependencies
- 新增 EventType：DEVICE_AFFECTED / DEVICE_RECOVERED / FAULT_PROPAGATED

## 流程设计
1. 定义依赖关系 → 存入device_dependencies表
2. 设备宕机 → 故障传播引擎遍历依赖树 → 标记所有下游设备is_affected=True
3. 下游设备告警触发 → 检查is_affected → 标记为衍生告警 → 抑制通知
4. 根因设备恢复 → 清除下游受影响标记 → 推送恢复事件
5. 前端拓扑图实时渲染依赖连线和传播状态

## 边界条件与异常处理
- 循环依赖检测：创建依赖时检查是否形成环，拒绝创建
- 多级传播：A→B→C三级依赖，A宕机时B和C都标记受影响
- 依赖关系变更时设备已宕机：重新计算传播范围
- 同一设备有多个父依赖：任一父宕机即标记受影响

## 验收标准
- 网关宕机后其下所有传感器设备标记为受影响状态
- 受影响传感器的告警标注为衍生告警，不单独推送通知
- 前端拓扑图显示依赖连线，根因红色脉冲、受影响橙色
- 网关恢复后传感器自动清除受影响标记
- 创建循环依赖时API返回400错误
