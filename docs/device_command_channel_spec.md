# 设备双向命令通道与OTA升级闭环需求规格

## 背景与目标
EdgeFleet-Simulator当前只有设备→平台的单向数据通道（MQTT遥测上报），平台无法向设备下发命令。运维无法远程重启设备、调整采集频率或推送固件升级。设备管理只有状态查看，没有远程操作能力。OTA升级完全靠人工逐台操作，无法批量推送和追踪升级进度。

需要实现设备双向命令通道和OTA升级闭环：平台通过MQTT向设备下发命令，设备执行后上报结果；OTA升级支持批量推送、进度追踪和自动回滚。

## 需求清单
- R-DC-01: 命令通道：平台通过MQTT向设备发布命令到topic devices/{device_id}/commands
- R-DC-02: 命令类型：重启、调整采集频率、切换模式、OTA升级
- R-DC-03: 命令响应：设备执行后通过MQTT上报结果到 devices/{device_id}/responses
- R-DC-04: 命令超时：命令下发后N秒未收到响应标记为超时
- R-DC-05: OTA升级流程：上传固件 → 创建升级任务 → 批量下发到目标设备 → 追踪进度
- R-DC-06: OTA进度：设备上报下载进度、校验结果、安装状态
- R-DC-07: OTA回滚：升级失败时自动回滚到上一版本
- R-DC-08: 前端设备详情页增加命令面板和OTA升级进度条
- R-DC-09: 命令和OTA操作记录审计日志

## 现有架构约束
- MQTT当前仅用于遥测上报（telemetry通道），需扩展命令通道
- 模拟器使用SensorModel和AnomalySensorModel，需增加命令处理逻辑
- 设备状态存储在PostgreSQL，命令记录需新增表
- WebSocket用于实时事件推送，OTA进度可通过此通道推送到前端

## 技术栈约束
- 后端：FastAPI + PostgreSQL + InfluxDB + Redis
- 消息协议：MQTT (Mosquitto)
- 设备模拟器：Python asyncio + paho-mqtt
- 前端：React + D3.js

## 数据模型变更
- 新表 device_commands：id, device_id, command_type, payload, status, issued_at, responded_at, result
- 新表 ota_tasks：id, firmware_url, firmware_version, target_device_ids (JSONB), status, created_at
- 新表 ota_progress：id, task_id, device_id, phase (DOWNLOAD/VERIFY/INSTALL/ROLLBACK), progress_pct, status, error_message
- Device模型新增：firmware_version, last_command_at
- 新增MQTT Topic：devices/{device_id}/commands, devices/{device_id}/responses
- 新增 EventType：COMMAND_ISSUED / COMMAND_COMPLETED / COMMAND_TIMEOUT / OTA_PROGRESS / OTA_COMPLETED

## 流程设计
1. 命令下发：API → 写入device_commands → MQTT发布到命令topic → 等待响应
2. 命令处理：模拟器订阅命令topic → 执行命令 → 发布响应到响应topic
3. 响应处理：后端订阅响应topic → 更新命令状态 → 推送WebSocket
4. OTA流程：上传固件 → 创建ota_task → 逐设备下发升级命令 → 追踪ota_progress
5. 回滚：设备上报安装失败 → 下发回滚命令 → 设备恢复旧版本

## 边界条件与异常处理
- 设备离线时下发命令：标记为PENDING，设备上线后补发
- 命令执行失败：记录错误信息，不自动重试，由运维决定
- OTA批量升级部分失败：成功的不回滚，失败的标记并推送告警
- 固件校验失败：自动回滚，上报校验错误
- 并发命令冲突：同一设备同时只执行一条命令，后续命令排队

## 验收标准
- 通过前端或API向在线设备下发重启命令，设备5秒内重启并上报结果
- 设备离线时下发命令，设备上线后自动接收并执行
- OTA批量升级3台设备，前端实时显示每台设备的下载和安装进度
- OTA安装失败的设备自动回滚到旧版本并上报错误
- 同一设备并发命令时排队执行而非并行
