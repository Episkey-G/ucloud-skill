# Tier-1 Product Workflows & Parameter Guide

This file covers the 6 most commonly used products. For these products, follow the workflow templates below instead of reading the summary file — this tells you exactly which APIs to call and in what order.

**For write operations**: after picking the API from the workflow below, fetch its full documentation via:
```bash
python3 <skill-path>/scripts/fetch_api_doc.py <Product> <ActionName>
```

**For read operations**: use `--fields` to reduce response size:
```bash
python3 <skill-path>/scripts/call_api.py <Action> '<params>' --fields field1,field2,...
```

---

## UHost (云主机) — 36 APIs

### 创建云主机（标准流程）
1. `DescribeImage` → 查询可用镜像，让用户从表格中选择
2. `DescribeAvailableInstanceTypes` → 可选：查询可售机型（如用户不确定配置）
3. `CreateUHostInstance` → 创建主机

### 创建云主机（最便宜/默认/随便开一台）
First confirm the user wants fast-create with minimum usable defaults. Only then read `references/fast-create-template.md` and follow it exactly.

The short version is:
1. `DescribeImage` → 选一个常用 Linux 基础镜像
2. `DescribeAvailableInstanceTypes` → 只调用一次，校验 cheapest template 是否兼容
3. `CreateUHostInstance` → 使用固定默认值创建

Default template:
- `MachineType=O`
- `CPU=1`
- `Memory=1024`
- `Disks=[{"IsBoot":"True","Type":"CLOUD_SSD","Size":20}]`
- `ChargeType=Dynamic`
- `Quantity=0`

Do not call price APIs for this path.

**参数陷阱：**
- `ImageId` 必须从 DescribeImage 获取，绝不能猜测
- `Password` 必须 base64 编码后传入
- `Disks` 是数组参数，至少需要一个系统盘：`[{"IsBoot":"True","Type":"CLOUD_SSD","Size":40}]`
- `MachineType` 常用值：`N`(通用型)、`C`(计算型)、`G`(GPU型)、`O`(快杰型)
- `MinimalCpuPlatform` 默认 `Intel/Auto`，一般不需要改
- `ChargeType` 默认 `Month`，`Quantity` 默认 `1`
- `LoginMode` 默认 `Password`，也支持 `KeyPair`

### 查询主机
- `DescribeUHostInstance` → 按 UHostIds/Tag/SubnetId/VPCId 过滤
- 返回字段包含：UHostId, Name, State, CPU, Memory, IPSet(IP地址), BasicImageId 等
- 推荐 `--fields UHostId,Name,State,CPU,Memory,IPSet`

### 开关机 / 重启
- `StartUHostInstance` → 启动（需要 UHostId）
- `StopUHostInstance` → 关机（需要 UHostId）
- `RebootUHostInstance` → 重启（需要 UHostId）
- `PoweroffUHostInstance` → 强制断电（慎用）

### 调整配置（升降级）
1. `GetUHostUpgradePrice` → 先查价格差额
2. `StopUHostInstance` → 需要先关机
3. `ResizeUHostInstance` → 修改 CPU/Memory 等
4. `StartUHostInstance` → 重新开机

### 重装系统
1. `DescribeImage` → 选择新镜像
2. `StopUHostInstance` → 需要先关机
3. `ReinstallUHostInstance` → 重装（需要 ImageId, Password）

### 删除主机
- `TerminateUHostInstance` → 删除（需要 UHostId）
- ⚠️ 不可逆操作，务必让用户确认

### 其他常用操作
- `ResetUHostInstancePassword` → 重置密码（base64编码）
- `ModifyUHostInstanceName` → 改名
- `GetUHostInstanceVncInfo` → 获取 VNC 登录地址
- `CreateCustomImage` → 从主机创建自定义镜像

---

## UDisk (云硬盘) — 21 APIs

### 创建云硬盘
- `CreateUDisk` → 独立创建（需手动挂载）
- `CreateAttachUDisk` → 创建并自动挂载到指定主机（更方便）

**参数陷阱：**
- `DiskType` 类型决定 Size 范围：
  - `DataDisk`(普通数据盘): 1-8000 GB
  - `SSDDataDisk`(SSD数据盘): 1-8000 GB
  - `RSSDDataDisk`(RSSD数据盘): 1-32000 GB
  - `EfficiencyDataDisk`(高效数据盘): 1-32000 GB
- `ChargeType` 默认 `Dynamic`(按时)，注意跟 UHost 默认 `Month` 不同

### 查询云硬盘
- `DescribeUDisk` → 列表/详情
- 推荐 `--fields UDiskId,Name,Status,Size,UHostId`

### 挂载 / 卸载
- `AttachUDisk` → 挂载到主机（需要 UHostId + UDiskId）
- `DetachUDisk` → 从主机卸载（需要 UHostId + UDiskId）
- `DetachDeleteUDisk` → 卸载并删除（合并操作）

### 扩容
- `DescribeUDiskUpgradePrice` → 查价格
- `ResizeUDisk` → 扩容（只能增大，不能缩小）

### 快照管理
1. `CreateUDiskSnapshot` → 创建快照
2. `DescribeUDiskSnapshot` → 查看快照列表
3. `CloneUDiskSnapshot` → 从快照克隆新磁盘
4. `DeleteUDiskSnapshot` → 删除快照

### 删除
- `DeleteUDisk` → 删除（必须先卸载）

---

## UNet / EIP (弹性IP) — 30 APIs

### 申请弹性 IP
- `AllocateEIP` → 申请新 EIP

**参数陷阱：**
- `OperatorName` 是必填项：`Bgp`(BGP线路,最常用) / `International`(国际) / `BGPPro`(精品BGP)
- `Bandwidth` 是必填项，单位 Mbps；共享带宽模式下必须填 0
- `PayMode`：`Bandwidth`(带宽计费,默认) / `Traffic`(流量计费) / `ShareBandwidth`(共享带宽)
- `ChargeType` 默认 `Dynamic`(按时)

### 绑定 / 解绑
- `BindEIP` → 绑定到资源（UHostId/ULBId 等）
- `UnBindEIP` → 解绑

### 调整带宽
- `GetEIPUpgradePrice` → 查价格
- `ModifyEIPBandwidth` → 调整带宽

### 释放 EIP
- `ReleaseEIP` → 释放（必须先解绑）

### 共享带宽
1. `AllocateShareBandwidth` → 创建共享带宽
2. `AssociateEIPWithShareBandwidth` → 将 EIP 加入共享带宽
3. `DisassociateEIPWithShareBandwidth` → 移出
4. `ResizeShareBandwidth` → 调整带宽
5. `ReleaseShareBandwidth` → 释放

### 防火墙
1. `CreateFirewall` → 创建防火墙规则组
2. `GrantFirewall` → 应用到资源（不是 BindFirewall！）
3. `UpdateFirewall` → 修改规则
4. `DisassociateFirewall` → 解绑
5. `DescribeFirewall` → 查询

---

## VPC (私有网络) — 97 APIs

### 创建 VPC + 子网
1. `CreateVPC` → 创建 VPC（Network 是数组，如 `["10.0.0.0/16"]`）
2. `CreateSubnet` → 在 VPC 下创建子网（需要 VPCId, Subnet CIDR）

**参数陷阱：**
- `Network` 是数组参数：`["10.0.0.0/16"]`
- VPC 创建后网段不能修改（只能追加：`AddVPCNetwork`）

### 查询
- `DescribeVPC` → VPC 列表
- `DescribeSubnet` → 子网列表
- `DescribeSubnetResource` → 子网下的资源

### 路由管理
1. `CreateRouteTable` → 创建自定义路由表
2. `ModifyRouteRule` → 增/删/改路由条目
3. `AssociateRouteTable` → 绑定到子网
4. `CloneRouteTable` → 复制路由表

### NAT 网关
1. `CreateNATGW` → 创建 NAT 网关（需要 EIPId, SubnetworkIds）
2. `CreateNATGWPolicy` → 添加端口转发规则（DNAT）
3. `AddSnatRule` → 添加 SNAT 出口规则
4. `DescribeNATGW` → 查询

### 安全组
1. `CreateSecGroup` → 创建安全组
2. `CreateSecGroupRule` → 添加规则
3. `AssociateSecGroup` → 绑定到资源
4. `DisassociateSecGroup` → 解绑

### 网络 ACL
1. `CreateNetworkAcl` → 创建 ACL
2. `CreateNetworkAclEntry` → 添加规则
3. `CreateNetworkAclAssociation` → 绑定到子网

### VPC 互通
1. `CreateVPCIntercom` → 建立 VPC 间互通
2. `DeleteVPCIntercom` → 删除互通

---

## ULB (负载均衡) — 47 APIs

ULB 有两种模型，API 命名不同：
- **CLB (传统型)**：使用 VServer 模型 → `CreateULB` + `CreateVServer` + `AllocateBackend`
- **ALB (应用型)**：使用 Listener 模型 → `DescribeLoadBalancers` + `DescribeListeners` + `DescribeRules`

### 创建传统型负载均衡 (CLB)
1. `CreateULB` → 创建 CLB 实例
2. `CreateVServer` → 创建监听器（指定协议 HTTP/HTTPS/TCP/UDP、端口、负载算法）
3. `AllocateBackend` → 添加后端节点（UHostId + Port + Weight）

**参数陷阱：**
- `ListenType`：`RequestProxy`(请求代理/七层,外网默认) / `PacketsTransmit`(报文转发/四层,内网默认)
- CreateVServer 的 `Method`(负载算法)：`Roundrobin`/`Source`/`WeightRoundrobin`/`Leastconn`/`Backup`
- AllocateBackend 的 `ResourceType`：`UHost`/`UNI`/`UPM`/`UHybrid`/`CUBE`/`IP`

### 查询负载均衡
- `DescribeULB` 或 `DescribeULBSimple` → CLB 列表
- `DescribeVServer` → VServer 详情（含后端节点和健康检查状态）
- `DescribeLoadBalancers` → ALB 列表
- `DescribeListeners` → ALB 监听器

### SSL 证书
1. `CreateSSL` → 上传 SSL 证书（PEM格式）
2. `BindSSL` → 绑定到 VServer（CLB）
3. `AddSSLBinding` → 绑定到 Listener（ALB）

### 内容转发（CLB）
1. `CreatePolicy` → 创建转发规则（基于 Host/Path）
2. `UpdatePolicy` → 修改规则
3. `DeletePolicy` → 删除规则

### 管理后端节点
- `UpdateBackendAttribute` → 修改权重、启用/禁用
- `ReleaseBackend` → 移除后端节点（CLB）
- `RemoveTargets` → 移除后端节点（ALB）

### 删除
- `DeleteULB` → 删除 CLB（需先删 VServer）
- `DeleteVServer` → 删除 VServer（需先移除后端）
- `DeleteLoadBalancer` → 删除 ALB
- `DeleteListener` → 删除 ALB 监听器

---

## UDB (云数据库 MySQL) — 61 APIs

### 创建数据库实例
1. `DescribeUDBParamGroup` → **必须先查配置参数组**，获取 ParamGroupId
2. `DescribeUDBType` → 可选：查看支持的 DB 类型
3. `ListUDBMachineType` → 可选：查看支持的机型规格
4. `CreateUDBInstance` → 创建实例

**参数陷阱：**
- `ParamGroupId` 是必填项！必须先调 DescribeUDBParamGroup 获取
- `DBTypeId` 必须是精确的版本字符串：`mysql-5.7` / `mysql-8.0` / `percona-5.7` 等
- `AdminPassword` 是必填项
- `Port` 默认 3306(MySQL) / 27017(MongoDB) / 5432(PostgreSQL)
- `DiskSpace` 单位 GB，范围 20-32000
- `MemoryLimit` 必须是特定值：2000/4000/6000/8000/12000/16000/24000/32000/48000/64000/96000/128000 (MB)
- `Name` 至少 6 个字符
- `InstanceMode`：`Normal`(普通) / `HA`(高可用)

### 查询数据库
- `DescribeUDBInstance` → 查列表（可按 ClassType/DBId 过滤）
- `DescribeUDBInstanceState` → 查运行状态
- 推荐 `--fields DBId,Name,State,DBTypeId,MemoryLimit,DiskSpace,VirtualIP`

### 创建从库（读副本）
- `CreateUDBSlave` → 从主库创建从库

### 备份与恢复
1. `BackupUDBInstance` → 手动触发备份
2. `DescribeUDBBackup` → 查看备份列表
3. `FetchUDBInstanceEarliestRecoverTime` → 获取最早可恢复时间点
4. `CreateUDBInstanceByRecovery` → 从备份恢复（创建新实例）
5. `RollbackUDBInstance` → 在原实例回档指定库表

### 读写分离
1. `EnableUDBRWSplitting` → 开启读写分离
2. `SetUDBRWSplitting` → 设置模式
3. `DescribeUDBSplittingInfo` → 查看详情
4. `DisableUDBRWSplitting` → 关闭

### 升级高可用
1. `CheckUDBInstanceToHAAllowance` → 检查是否可升级
2. `PromoteUDBInstanceToHA` → SSD 实例升级 HA
3. `UpgradeUDBInstanceToHA` → NVMe 实例升级 HA

### 调整配置
1. `DescribeUDBInstanceUpgradePrice` → 查升降级价格
2. `ResizeUDBInstance` → 调整内存/磁盘/机型

### 参数配置管理
- `DescribeUDBParamGroup` → 查看参数组详情
- `CreateUDBParamGroup` → 从已有参数组创建新的
- `UpdateUDBParamGroup` → 修改参数值
- `ChangeUDBParamGroup` → 给实例切换参数组

### 实例管理
- `StartUDBInstance` / `StopUDBInstance` / `RestartUDBInstance` → 启停重启
- `ModifyUDBInstanceName` → 改名
- `ModifyUDBInstancePassword` → 改密码
- `DeleteUDBInstance` → 删除
- `PromoteUDBSlave` → 从库提升为独立库

### 日志管理
- `DescribeUDBInstanceLog` → 查看错误日志/慢查询日志
- `BackupUDBInstanceSlowLog` → 备份慢查询分析
- `ClearUDBLog` → 清理日志
