---
name: ucloud
description: Manage UCloud cloud resources (virtual machines, networks, disks, databases, load balancers, containers, CDN, and 43 other cloud products) through natural language. Use this skill whenever the user wants to create, query, modify, or delete any UCloud cloud resource. Trigger on mentions of UCloud, UHost, VPC, UDB, UDisk, EIP, ULB, UK8S, UMem, or any UCloud product name. Also trigger when the user says things like "check my cloud servers", "spin up a new instance", "release that elastic IP", "resize the database", "list my disks", or any cloud infrastructure management task targeting UCloud. Even if the user just says "check my hosts" or "delete that machine" in a UCloud project context, this skill should activate.
allowed-tools: Bash(python *)
---

# UCloud Resource Manager

Manage 900+ UCloud APIs across 40+ products. The product catalog is built at runtime from the remote GitHub registry, so new products appear automatically. API docs are fetched on-demand from GitHub.

All script paths use `<skill-path>` as a placeholder — the skill framework resolves it at runtime. Only use the 4 scripts listed below; never invent script names or guess parameter values.

| Script | Purpose | When |
|--------|---------|------|
| `route_product.py <keyword>` | Identify product + list APIs | Step 1 |
| `fetch_api_doc.py <Product> <Action>` | Fetch API doc + inject hints | Step 2 (write ops) |
| `gen_password.py` | Random password + base64 | Create with password |
| `call_api.py <Action> '<params>' [--fields] [--all-projects]` | Execute API call | Step 3 |

## Setup

Check environment variables before proceeding:
- `UCLOUD_PUBLIC_KEY` / `UCLOUD_PRIVATE_KEY` (required) — `call_api.py` reads these automatically for signature calculation
- `UCLOUD_REGION` (optional) — fallback default region
- `UCLOUD_PROJECT_ID` (optional) — fallback default project

**Environment probe** (once per session, when Region and ProjectId are both unset):

```bash
python3 <skill-path>/scripts/call_api.py GetProjectList '{"Limit":100}'
python3 <skill-path>/scripts/call_api.py ListRegions '{}'
```

Cache the resolved Region and ProjectId for all subsequent calls. If multiple projects exist, ask the user to choose. If the user specifies a region, use it directly; if not and `UCLOUD_REGION` is unset, ask.

## Workflow Overview

```
User request
    │
    ├─ Read (Get/Describe/List/Query/Check)
    │   Step 1 → route_product.py
    │   Step 2 → skip
    │   Step 3 → call_api.py --fields --all-projects
    │
    ├─ Create / Modify
    │   Step 1 → route_product.py
    │   Step 2 → fetch_api_doc.py → execute prerequisites → build params → confirm
    │   Step 3 → call_api.py (after YES)
    │
    ├─ Delete (Terminate/Release/Remove/Destroy/Delete/...)
    │   Step 1 → route_product.py
    │   Step 2 → describe resource → warn irreversible → confirm (mandatory, even if user says "直接删")
    │   Step 3 → call_api.py (after YES)
    │
    └─ Fast Create ("最便宜" / "最小配置" / "默认配置" / vague create with missing specs)
        Step 1 → route_product.py
        Ask user: "是否按最小可用默认配置快速创建？" — only load fast-create template after explicit YES
        Step 2 → minimum live checks per template → confirm
        Step 3 → call_api.py (after YES)
```

Multi-product requests (e.g., "create host + bind EIP + attach disk"): handle each sub-task sequentially, extracting resource IDs from each response to chain into the next step.

## Step 1: Route to Product

```bash
python3 <skill-path>/scripts/route_product.py <keyword>
```

Output scenarios:
- **Single match** — product name, tier-1 flag, API list, `[System Hint]` SOP
- **Multiple matches** — candidates listed; ask user to clarify
- **No match** — all products listed by category; retry with a different keyword

For **tier-1 products**: also read `<skill-path>/references/tier1-workflows.md` for pre-built workflow templates.

**Speed tip**: combine routing and doc fetch in one call when you already know the action:
```bash
python3 <skill-path>/scripts/route_product.py uhost && \
python3 <skill-path>/scripts/fetch_api_doc.py UHost CreateUHostInstance
```

## Step 2: Pre-flight Checklist (write operations only)

Skip this step for read operations — go directly to Step 3.

Write operations cost money and fail silently when parameters are wrong. Cloud inventory changes in real-time — what worked yesterday may not work today. This checklist catches mismatches before they become API errors or billing surprises.

### 2a. Fetch API Documentation

```bash
python3 <skill-path>/scripts/fetch_api_doc.py <Product> <ActionName>
```

Read both the `[System Hint]` block and the parameter table. Hints encode hard-won knowledge about prerequisites that the API doc alone doesn't make obvious.

### 2b. Execute All Prerequisites

The `[System Hint]` block lists prerequisite API calls (e.g., DescribeImage, DescribeAvailableInstanceTypes). Execute every single one before constructing parameters — this is not optional.

Why: a region may support 64-core but not 128-core, a zone may be sold out of SSD, an image may be deprecated. Prerequisite calls catch these mismatches upfront instead of getting a cryptic `RetCode: 8357` after the user has already confirmed.

If a required parameter needs a business ID you don't have (ImageId, VPCId, SubnetId), call the corresponding Describe API and present options to the user.

### 2c. Build Parameters

Construct params JSON strictly from the parameter table:
- All required params (marked **Yes**) must be provided
- Nested arrays (e.g., `Disks.N.IsBoot`) — pass as JSON arrays; `call_api.py` auto-flattens
- Billing defaults: `ChargeType=Month`, `Quantity=1`
- Password generation when `LoginMode=Password` and user hasn't provided one:
  ```bash
  python3 <skill-path>/scripts/gen_password.py
  ```

Read `<skill-path>/references/parameter-guide.md` only when you need guidance on complex arrays, billing, or confirmation formatting.

### 2d. Confirm Before Execution

Present a Markdown table summarizing all parameters:

| Parameter | Value | Description |
|-----------|-------|-------------|
| Region | cn-bj2 | 地域 |
| CPU | 2 | CPU核数 |
| ChargeType | Month | 按月付费 |

Follow with cost implications. Do not execute without explicit YES. If a password was generated, note it will be shown after creation.

Write-operation guardrails:
- Never call pricing APIs unless the user explicitly asks for cost comparison
- Never retry a write operation with guessed parameter changes
- Never translate region names from memory — use live API output
- Never silently convert a vague request into fast-create — ask first

## Step 3: Execute

### Broad vs. Targeted Queries

UCloud resources are isolated by project. When the user's phrasing implies broad scope ("所有", "我的", "有哪些", "list my"), use `--all-projects`:

```bash
python3 <skill-path>/scripts/call_api.py DescribeUHostInstance \
  '{"Region":"cn-bj2","Limit":20}' \
  --fields UHostId,Name,State,CPU,Memory,IPSet --all-projects
```

Only query a single project when the user targets a specific resource or names a project explicitly.

### API Call Patterns

```bash
# Read — filter to key fields (always include Limit: 20)
python3 <skill-path>/scripts/call_api.py DescribeUHostInstance \
  '{"Region":"cn-bj2","Limit":20}' --fields UHostId,Name,State,CPU,Memory,IPSet

# Write — no --fields needed
python3 <skill-path>/scripts/call_api.py CreateUHostInstance '{"Region":"cn-bj2",...}'
```

Use `--fields` for read operations to filter responses. Always include key identifiers (resource ID, Name, State).

## Step 4: Handle the Response

- **`RetCode: 0`** = success. Extract key info (resource IDs, IPs, status) and present as a table.
- **`RetCode: non-zero`** = error. The script provides two levels of help:
  - `[Auto-Fix Suggestion]` — specific commands to resolve the issue; follow them
  - `[System Hint]` — error diagnosis with reference links for context
- **Auto-fix** (handled transparently by `call_api.py`): missing ProjectId/Region/Zone triggers automatic lookup and retry
- **If a password was generated**: display it in plaintext — user's only chance to see it
- **Empty results with cross-project suggestion**: follow it — the resource may exist in another project

## References (load on demand)

| File | Content | When to read |
|------|---------|--------------|
| `references/tier1-workflows.md` | UHost, UDisk, UNet, VPC, ULB, UDB workflows | Tier-1 product operations |
| `references/fast-create-template.md` | Deterministic fast-create workflow | User agrees to fast-create |
| `references/parameter-guide.md` | Arrays, billing, confirmation formatting | Complex write operations |
