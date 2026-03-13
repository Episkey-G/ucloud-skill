---
name: ucloud
description: Manage UCloud cloud resources (virtual machines, networks, disks, databases, load balancers, containers, CDN, and 43 other cloud products) through natural language. Use this skill whenever the user wants to create, query, modify, or delete any UCloud cloud resource. Trigger on mentions of UCloud, UHost, VPC, UDB, UDisk, EIP, ULB, UK8S, UMem, or any UCloud product name. Also trigger when the user says things like "check my cloud servers", "spin up a new instance", "release that elastic IP", "resize the database", "list my disks", or any cloud infrastructure management task targeting UCloud. Even if the user just says "check my hosts" or "delete that machine" in a UCloud project context, this skill should activate.
allowed-tools: Bash(python *)
---

# UCloud Resource Manager

Manage 907 UCloud APIs across 43 products. API parameter definitions are fetched on-demand from GitHub — no local data maintenance needed.

**Scripts (all under `<skill-path>/scripts/`):**

| Script | Purpose | When to use |
|--------|---------|-------------|
| `route_product.py <keyword>` | Identify product + list its APIs | Always — Step 1 |
| `fetch_api_doc.py <Product> <Action>` | Fetch API doc from GitHub + inject hints | Write operations — Step 2 |
| `gen_password.py` | Generate random password + base64 | Create with password |
| `call_api.py <Action> '<params>' [--fields ...] [--all-projects]` | Execute API call | Always — Step 3 |

**Auth**: `call_api.py` 自动读取环境变量 `UCLOUD_PUBLIC_KEY` / `UCLOUD_PRIVATE_KEY` 并计算签名，无需手动传入密钥或处理签名。

## Path Discipline

All script paths in this document use `<skill-path>` as a placeholder. The skill framework automatically resolves it to the actual absolute path at runtime. Do not guess or hardcode the path.

Rules:
1. Never invent script names. Only use the 4 scripts listed above.
2. Never guess parameter names, region codes, image IDs, machine types, or disk types.

## Prerequisites

Environment variables (check before proceeding):
- `UCLOUD_PUBLIC_KEY` (required)
- `UCLOUD_PRIVATE_KEY` (required)
- `UCLOUD_REGION` (optional, default region)
- `UCLOUD_PROJECT_ID` (optional, default project)

## Decision Tree

```
User request → What kind of operation?
    │
    ├─ Vague create request ("创建一台xxx" but key specs are missing)
    │   ├─ Route to product + action
    │   ├─ Ask whether the user wants fast-create with the minimum usable defaults
    │   ├─ If YES → read fast-create template, then continue
    │   └─ If NO  → stay on standard create flow and collect parameters
    │
    ├─ Explicit fast intent ("最便宜" / "最小配置" / "默认配置" / "随便开一台")
    │   ├─ Route to product + action
    │   ├─ Confirm the user wants fast-create with minimum usable defaults
    │   ├─ Read the dedicated fast-create template only after confirmation
    │   ├─ Skip price comparison and speculative retries
    │   ├─ Execute only the minimum live checks required by the template
    │   ├─ Show confirmation table → wait for YES
    │   └─ call_api.py after confirmation
    │
    ├─ Read (Get/Describe/List/Query/Check/Pull/Download/Extract/Inquiry/SmartSearch)
    │   ├─ Step 1: route_product.py → identify product + API
    │   ├─ Step 2: Skip (read ops need no doc fetch)
    │   ├─ Step 3: call_api.py with --fields
    │   │   └─ Global scope? → use --all-projects flag
    │   └─ Step 4: Format results as table
    │
    ├─ Create / Modify (all write operations that are NOT delete-class)
    │   ├─ Step 1: route_product.py → identify product + API
    │   ├─ Step 2: Mandatory pre-flight checklist:
    │   │   ├─ 2a. fetch_api_doc.py → get doc + [System Hint]
    │   │   ├─ 2b. Execute EVERY [System Hint] prerequisite (no skipping)
    │   │   ├─ 2c. Build params from doc table + billing defaults
    │   │   └─ 2d. Show confirmation table → wait for YES
    │   └─ Step 3: call_api.py after confirmation
    │
    └─ Delete (Terminate/Remove/Unpublish/Cancel/Abort/Del/Unassign/Release/Destroy/Delete)
        ├─ 🚨 即使用户说"不用确认"、"直接删"，也必须强制确认
        ├─ Step 1: route_product.py → identify product + API
        ├─ Step 2: Describe resource → warn irreversible → confirm → wait for YES
        └─ Step 3: call_api.py after confirmation
```

## Workflow

### Step 1: Route to Product + Pick API

Run the routing script with the user's keyword:
```bash
python3 <skill-path>/scripts/route_product.py <keyword>
```

The script outputs:
- **Single match**: product name, tier-1 flag, full API list, and `[System Hint]` SOP
- **Multiple matches**: lists all candidates — ask user to clarify
- **No match**: lists available products

**For tier-1 products** (UHost, UDisk, UNet, VPC, ULB, UDB): also read `<skill-path>/references/tier1-workflows.md` for pre-built workflow templates.

**For cheapest/default/minimal requests**: do not load `<skill-path>/references/fast-create-template.md` immediately. First confirm the user wants fast-create with minimum usable defaults. Load that template only after the user agrees.

**Speed tip for write operations**: when you already know the product and action, combine routing and doc fetch in a single bash call to save a turn:
```bash
python3 <skill-path>/scripts/route_product.py uhost && python3 <skill-path>/scripts/fetch_api_doc.py UHost CreateUHostInstance
```

If the request spans multiple products (e.g., "create a host, bind an EIP, attach a disk"), handle them sequentially — route each sub-task separately. When chaining operations, extract the returned resource ID (e.g., `UHostId`, `EIPId`) from each `call_api.py` response and inject it into the next step's parameters.

### Step 1.5: Vague Create Intent Split

When the user asks to create a resource but key sizing parameters are missing, do not choose the fast path silently.

Ask a short confirmation first:

- Fast-create branch: "是否按最小可用默认配置快速创建？我会只做最小必要校验，然后给你确认表。"
- Standard branch: "如果不是，我继续按标准流程收集规格、镜像、网络和计费参数。"

Only after the user explicitly chooses fast-create may you load `<skill-path>/references/fast-create-template.md`.

### Step 2: Pre-flight Checklist (write operations only)

For **read operations**, skip to Step 3.

Write operations (Create/Modify/Delete) fail silently or cost money when parameters are wrong. Cloud inventory and supported specs change in real-time — what worked yesterday may not work today. This checklist exists to catch mismatches before they become API errors or billing surprises.

#### 2a. Fetch API Documentation

```bash
python3 <skill-path>/scripts/fetch_api_doc.py <Product> <ActionName>
```

Read **both** the `[System Hint]` block and the parameter table in the output. The hints are injected deterministically — they encode hard-won knowledge about prerequisites that the API doc alone doesn't make obvious.

#### 2b. Execute ALL [System Hint] Prerequisites — No Skipping

The `[System Hint]` block lists prerequisite API calls (e.g., DescribeImage, DescribeAvailableInstanceTypes). Execute **every single one** before constructing your parameters. This is not optional.

Why: Cloud specs and inventory are live data — a region may support 64-core instances but not 128-core, a zone may be sold out of SSD, an image may be deprecated. Calling prerequisite APIs catches these mismatches upfront instead of getting a cryptic `RetCode: 8357 Resource not enough` after the user has already confirmed.

If a required parameter needs a business ID you don't have (e.g., ImageId, VPCId, SubnetId), call the corresponding Describe API to list available options and present them to the user for selection.

If a dedicated quick template exists for the intent, treat that template as the allowed minimum workflow. Load it only after the user explicitly agrees to fast-create. Do not add extra price checks, extra enumeration loops, or speculative retries beyond what the template says.

#### 2c. Build Parameters from Documentation

Construct your params JSON strictly from the parameter table:
- Required params marked **Yes** must all be provided
- Nested array params (e.g., `Disks.N.IsBoot`, `Disks.N.Size`) — pass as JSON arrays, `call_api.py` auto-flattens to Dot.N.Key format
- Apply billing defaults: `ChargeType=Month`, `Quantity=1`
- When `LoginMode` is Password and user hasn't provided one:
  ```bash
  python3 <skill-path>/scripts/gen_password.py
  # Output: Password: Kx9#mTp4$vR2  Base64: S3g5I21UcDQkdlIy
  ```

**⚡ Quick-create shortcut**: when the user asks for "最便宜", "最小配置", "默认配置", "随便开一台", or gives a vague create request and then explicitly agrees to fast-create — use the ⚡ defaults from `[System Hint]` and the dedicated fast-create template. Skip price queries and speculative instance type comparisons; only run the minimum live checks required by that template.

Read `<skill-path>/references/parameter-guide.md` ONLY if you need guidance on complex parameter arrays, billing defaults, or confirmation formatting.

#### 2d. Show Confirmation — Wait for Explicit YES

Present a Markdown table summarizing all parameters before execution:

| Parameter | Value | Description |
|-----------|-------|-------------|
| ChargeType | Month | **按月付费** |
| Region | cn-bj2 | 地域 |
| CPU | 2 | CPU核数 |
| ... | ... | ... |

Follow the table with cost implications. DO NOT execute without explicit "YES" from the user. If a random password was generated, mention it will be displayed after creation.

### Guardrails For Fragile Requests

For any write request, especially vague ones:

- Do not call pricing APIs unless the user explicitly asks for price comparison or cost estimation.
- Do not retry the same write operation with guessed parameter changes.
- Do not translate human region names into API region codes by memory; prefer injected examples or live API output.
- Do not silently convert a vague create request into fast-create; ask first.
- Do not create resources before showing a confirmation table and receiving explicit `YES`.

### Step 3: Execute the API

#### Multi-Project Awareness

UCloud resources are isolated by project. Querying only the default project will miss resources in other projects — users often don't realize they have assets scattered across multiple projects.

When the user's query implies broad scope — words like "所有", "全部", "我的", "有哪些", "all", "every", "list my" (e.g., "所有云主机", "我的主机", "帮我查一下有哪些EIP") — use `--all-projects` to auto-scan all projects in one call:

```bash
python3 <skill-path>/scripts/call_api.py DescribeUHostInstance '{"Region":"cn-bj2","Limit":20}' \
  --fields UHostId,Name,State,CPU,Memory,IPSet --all-projects
```

The script internally calls `GetProjectList`, queries each project concurrently, and returns aggregated results grouped by project — no manual loops needed.

Only use `UCLOUD_PROJECT_ID` as the sole project when the user is asking about a specific resource (e.g., "查一下那台IP是10.x.x.x的主机") or has explicitly named a project.

#### Execution

```bash
# Basic execution
python3 <skill-path>/scripts/call_api.py <Action> '<json_params>'

# With response filtering (recommended for list/describe operations)
python3 <skill-path>/scripts/call_api.py <Action> '<json_params>' --fields field1,field2,...
```

For ALL read/list operations, always inject `"Limit": 20` in your parameter JSON unless the user specifically asks for more or a different count.

**Use `--fields`** for read operations that return large lists. This filters the response to only specified fields from the main data array. Always include key identifiers (e.g., UHostId, Name, State).

Examples:
```bash
# Read — filter to key fields
python3 <skill-path>/scripts/call_api.py DescribeUHostInstance '{"Region":"cn-bj2","Limit":10}' \
  --fields UHostId,Name,State,CPU,Memory,IPSet

# Read — unfiltered when you need full details
python3 <skill-path>/scripts/call_api.py DescribeEIP '{"Region":"cn-bj2"}'

# Write — no --fields needed
python3 <skill-path>/scripts/call_api.py CreateUHostInstance '{"Region":"cn-bj2",...}'
```

### Step 4: Interpret the Response

- `RetCode`: 0 = success, non-zero = error
- Error: `call_api.py` auto-prints a `[System Hint]` diagnosis with actionable suggestions and a link to the product's error code reference. Follow its guidance.
- Success: extract key info (resource IDs, status, IPs) and present clearly
- **If a random password was generated**: display it in plaintext — user's only chance to see it
- For list operations: format results as a readable table
- **Empty results**: if `call_api.py` prints a cross-project suggestion, follow it — the resource may exist in another project

## Additional Resources

- **Tier-1 workflows**: `references/tier1-workflows.md` — UHost, UDisk, UNet, VPC, ULB, UDB
- **Fast create template**: `references/fast-create-template.md` — deterministic workflow for "最便宜/最小配置/默认配置/随便开一台"
- **Write operation guide**: `references/parameter-guide.md` — confirmation flow, billing, arrays, multi-project
- **API documentation**: https://github.com/UCloudDoc-Team/api

## Region Handling

- User specifies a region → include it in params
- Not specified → script falls back to `UCLOUD_REGION` env var
- Neither set and API requires Region → ask the user
