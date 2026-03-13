# Write Operation Guide

Detailed parameter preparation, confirmation flow, and special handling rules for UCloud write operations (create/modify/delete). The main SKILL.md references this file — read it when handling any write operation.

## Gather Missing Parameters (Step 4a)

Read the API's `Request` array. Each parameter has `Name`, `Type`, `Desc`, and `Required`.

For parameters the user hasn't specified:

### Parameters that need a lookup query

Some required parameters (like `ImageId`) can't be guessed — call a read API first to get valid options. Present results as a table for the user to pick from.

Example: user wants to create a UHost but didn't specify an image:
```bash
python3 <skill-path>/scripts/call_api.py DescribeImage '{"Region":"cn-bj2","ImageType":"Base","OsType":"Linux","Limit":10}'
```

Then show:
```
可用镜像:
| # | ImageId        | 系统           | 说明               |
|---|----------------|----------------|--------------------|
| 1 | uimage-abc123  | Ubuntu 22.04   | 64位               |
| 2 | uimage-def456  | CentOS 7.9     | 64位               |
| 3 | uimage-ghi789  | Debian 12      | 64位               |
请选择镜像编号，或输入自定义 ImageId:
```

### Parameters with enum values

The `Desc` field often lists valid choices. Present them directly. For example, `MachineType` has `["N", "C", "G", "O"]` — show each option with its meaning from the Desc.

### Parameters with sensible defaults

Use them, but show them in the confirmation summary. For instance, `MachineType` defaults to "N" (通用型).

### Parameters to skip

- Internal: marked `【内部参数】` or `【内部api参数】` in Desc
- Deprecated: marked `【已废弃】` or `【待废弃】`

---

## Password Handling (Step 4b)

When a create operation requires login credentials (e.g., `LoginMode` for UHost):

1. Default `LoginMode` to `Password` unless the user asks for key-pair login.
2. If the user provided a password, base64-encode it and use it.
3. If the user did NOT provide a password, ask:
   ```
   登录密码未设置，请选择:
   1. 输入自定义密码
   2. 自动生成随机密码（创建完成后会告知密码）
   ```
4. **Random password generation**: 12-character password that satisfies UCloud requirements:
   - At least 1 uppercase letter, 1 lowercase letter, 1 digit, 1 special character from `!@#$%^&*`
   - No spaces or ambiguous characters (0/O, l/1)
   - Example: `Kx9#mTp4$vR2`
5. Base64-encode before sending: `echo -n 'Kx9#mTp4$vR2' | base64`
6. **After successful creation, display the password in plaintext** — this is the user's only chance to see it:
   ```
   ✅ 云主机创建成功!
   - 资源ID: uhost-xxxx
   - 登录密码: Kx9#mTp4$vR2  ← 请立即保存，后续无法找回
   ```

---

## Billing Defaults (Step 4c)

For create operations that involve billing (ChargeType/Quantity parameters):

- Default `ChargeType` to `Month` (按月付费)
- Default `Quantity` to `1` (1个月)
- These defaults must appear **prominently** in the confirmation summary — users need to consciously agree to how they'll be billed.

---

## Confirmation Summary (Step 4d)

Present a clear summary with all parameters grouped by category. Billing goes at the top since it involves money:

```
📋 即将执行: CreateUHostInstance (创建云主机)

💰 计费方式:
  - ChargeType: Month (按月付费)
  - Quantity: 1 个月
  ⚠️ 请确认计费方式是否正确

🖥️ 主机配置:
  - Region: cn-bj2 (北京二)
  - Zone: cn-bj2-05 (可用区E)
  - CPU: 2 核
  - Memory: 4096 MB (4 GB)
  - MachineType: N (通用型)
  - ImageId: uimage-xxx (Ubuntu 22.04)

💾 磁盘:
  - 系统盘: CLOUD_SSD, 40 GB

🔐 登录:
  - LoginMode: Password
  - Password: (已设置, base64编码)

确认创建? (y/n)
```

Only proceed after explicit user confirmation. If they want to change anything, go back to the relevant step.

---

## Array Parameter Format

When an API has array-type parameters (like Disks, NetworkInterface), pass them as JSON arrays. The script automatically flattens them:

```
Input:  {"Disks": [{"IsBoot": "True", "Type": "CLOUD_SSD", "Size": 20}]}
Sends:  Disks.0.IsBoot=True&Disks.0.Type=CLOUD_SSD&Disks.0.Size=20
```

Simple arrays: `{"PrivateIp": ["10.0.0.1", "10.0.0.2"]}` → `PrivateIp.0=10.0.0.1&PrivateIp.1=10.0.0.2`

### Complex Nested Parameter Examples

**多硬盘配置（系统盘 + 数据盘）**：
```json
{
  "Disks": [
    {"IsBoot": "True", "Type": "CLOUD_SSD", "Size": 40},
    {"IsBoot": "False", "Type": "CLOUD_SSD", "Size": 100}
  ]
}
```
展平后：`Disks.0.IsBoot=True&Disks.0.Type=CLOUD_SSD&Disks.0.Size=40&Disks.1.IsBoot=False&Disks.1.Type=CLOUD_SSD&Disks.1.Size=100`

**创建主机时绑定 EIP（NetworkInterface 数组）**：
```json
{
  "NetworkInterface": [
    {
      "EIP": {
        "OperatorName": "Bgp",
        "Bandwidth": 10
      }
    }
  ]
}
```
展平后：`NetworkInterface.0.EIP.OperatorName=Bgp&NetworkInterface.0.EIP.Bandwidth=10`

---

## Multi-Project Awareness

UCloud accounts often have multiple projects. A user asking "show me all my hosts" expects to see hosts across all projects.

**Before executing read operations (Describe/List/Get), check the project context:**

1. User specifies a project → use it directly
2. `UCLOUD_PROJECT_ID` is set → use it, mention results are scoped to that project
3. `UCLOUD_PROJECT_ID` is NOT set and user's intent is broad ("all my hosts", "有哪些") →
   - Call `GetProjectList '{}'` to list all projects
   - Run the query against each project
   - Aggregate and present results grouped by project

Cross-project scan is only needed for broad read operations. For create/modify/delete, a single project context is sufficient.
