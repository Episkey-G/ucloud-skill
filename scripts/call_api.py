#!/usr/bin/env python3
"""Execute a UCloud API call with automatic signature calculation and array flattening.

Features:
  --fields field1,field2,...   Filter response to specified fields
  --all-projects               Auto-scan all projects (GetProjectList + iterate)
  Auto-fix: missing ProjectId/Region/Zone are resolved automatically when possible.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional


API_ENDPOINT = "https://api.ucloud.cn"

# Delete-class prefixes — any action starting with these requires forced confirmation
# fmt: off
DELETE_PREFIXES = [
    "Terminate", "Remove", "Unpublish", "Cancel", "Abort", "Del",
    "Unassign", "Release", "Destroy", "Delete",
]
# fmt: on

# Common error codes with actionable hints.
# For product-specific codes, we generate a GitHub doc link.
COMMON_ERROR_HINTS = {
    100: "缺少必填参数 — 请检查 API 文档中标记为 Required 的参数是否都已提供。",
    110: "无效 Action — API 名称拼写错误，请用 route_product.py 确认正确的 API 名。",
    120: "缺少 Signature — 内部错误，请检查 UCLOUD_PRIVATE_KEY 是否正确设置。",
    130: "Signature 校验失败 — 请检查 UCLOUD_PUBLIC_KEY 和 UCLOUD_PRIVATE_KEY 是否匹配。",
    140: "超出 API 频率限制 — 请稍后重试。",
    150: "Service unavailable — UCloud 服务暂时不可用，请稍后重试。",
    160: "Action 不存在 — 此产品不支持该操作，请用 route_product.py 确认可用 API 列表。",
    161: "Action 未找到 — 检查 API 名称拼写是否正确。",
    170: "缺少必填参数 — 请对照 fetch_api_doc.py 输出的参数表检查。",
    171: "Signature 错误 — 检查 PublicKey/PrivateKey 环境变量。",
    172: "权限不足 — 当前账号/项目无此操作权限，请联系管理员。",
    173: "账号未实名认证 — 请先完成实名认证。",
    174: "Token 过期 — 请刷新凭证。",
    292: "项目不存在 — 检查 ProjectId 是否正确。",
    8095: "配额不足 — 当前项目的资源配额已满，请联系管理员提升配额或释放闲置资源。",
    8104: "存在未支付订单 — 请先完成待支付订单。",
    8116: "未开通按时计费权限 — 请在控制台开通后重试。",
    8226: "需要实名认证 — 请先完成实名认证。",
}

# Patterns in error Message that suggest specific actions
ERROR_MESSAGE_PATTERNS = [
    (re.compile(r"not enough|insufficient|资源不足|售罄", re.I),
     "该可用区资源可能不足，建议尝试其他可用区或调整配置。"),
    (re.compile(r"balance|余额|欠费", re.I),
     "账户余额不足，请提示用户前往控制台充值。"),
    (re.compile(r"stopped|关机|stop", re.I),
     "操作需要资源处于关机状态，请先执行 Stop 操作。"),
    (re.compile(r"running|开机", re.I),
     "操作需要资源处于运行状态，请先执行 Start 操作。"),
    (re.compile(r"bindip|bindEIP|bindULB", re.I),
     "操作需要资源已绑定相关资源，请先检查资源绑定状态。"),
]


def flatten_params(params: dict, prefix: str = "") -> dict:
    """Flatten nested dicts and arrays into UCloud's Dot.N.Key format.

    Examples:
        {"Disks": [{"IsBoot": "True", "Size": 20}]}
        → {"Disks.0.IsBoot": "True", "Disks.0.Size": 20}

        {"PrivateIp": ["10.0.0.1", "10.0.0.2"]}
        → {"PrivateIp.0": "10.0.0.1", "PrivateIp.1": "10.0.0.2"}
    """
    flat = {}
    for key, value in params.items():
        full_key = f"{prefix}{key}"

        if isinstance(value, list):
            for i, item in enumerate(value):
                item_key = f"{full_key}.{i}"
                if isinstance(item, dict):
                    flat.update(flatten_params(item, f"{item_key}."))
                else:
                    flat[item_key] = item
        elif isinstance(value, dict):
            flat.update(flatten_params(value, f"{full_key}."))
        else:
            flat[full_key] = value

    return flat


def any2string(value) -> str:
    """Convert any value to string for signature calculation."""
    if value is None:
        return ""
    elif isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, str):
        return value
    else:
        return str(value)


def calculate_signature(params: dict, private_key: str) -> str:
    """Calculate UCloud API signature.

    Algorithm: sort keys → concatenate key+value → append private_key → SHA1 hex.
    """
    sorted_keys = sorted(params.keys())
    items = "".join(f"{k}{any2string(params[k])}" for k in sorted_keys)
    origin = items + private_key
    return hashlib.sha1(origin.encode()).digest().hex()


def call_api(action: str, params: dict) -> dict:
    public_key = os.environ.get("UCLOUD_PUBLIC_KEY")
    private_key = os.environ.get("UCLOUD_PRIVATE_KEY")

    if not public_key or not private_key:
        return {"error": "Missing UCLOUD_PUBLIC_KEY or UCLOUD_PRIVATE_KEY environment variables"}

    # Merge defaults from env if not in params
    if "Region" not in params and os.environ.get("UCLOUD_REGION"):
        params["Region"] = os.environ["UCLOUD_REGION"]
    if "ProjectId" not in params and os.environ.get("UCLOUD_PROJECT_ID"):
        params["ProjectId"] = os.environ["UCLOUD_PROJECT_ID"]

    # Flatten nested arrays/dicts
    flat_params = flatten_params(params)

    # Inject public params
    flat_params["Action"] = action
    flat_params["PublicKey"] = public_key

    # Calculate signature
    flat_params["Signature"] = calculate_signature(flat_params, private_key)

    # Send request
    query_string = urllib.parse.urlencode(flat_params)
    url = f"{API_ENDPOINT}?{query_string}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}: {body}"}
    except urllib.error.URLError as e:
        return {"error": f"Network error: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def _get_github_path_for_action(action: str) -> str | None:
    """Look up which product owns a given action via the remote registry.

    Falls back gracefully if registry is unavailable (network issues, etc.).
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from registry import get_github_path_for_action
        return get_github_path_for_action(action)
    except Exception:
        return None


def diagnose_error(result: dict, action: str) -> None:
    """Print actionable diagnosis when RetCode != 0."""
    ret_code = result.get("RetCode", 0)
    message = result.get("Message", "")

    if ret_code == 0:
        return

    hints = []

    # Check known error code
    if ret_code in COMMON_ERROR_HINTS:
        hints.append(COMMON_ERROR_HINTS[ret_code])

    # Check message patterns for additional context
    for pattern, suggestion in ERROR_MESSAGE_PATTERNS:
        if pattern.search(message):
            hints.append(suggestion)
            break  # one pattern match is enough

    # Generate product-specific error doc link via remote registry
    github_path = _get_github_path_for_action(action)
    if github_path:
        doc_url = f"https://github.com/UCloudDoc-Team/api/blob/master/{github_path}/error_code.md"
        hints.append(f"完整错误码参考: {doc_url}")

    if hints:
        print(f"\n{'='*50}")
        print(f"[System Hint] 错误诊断 (RetCode: {ret_code}):")
        for h in hints:
            print(f"  ⚠ {h}")
        print("=" * 50)

    # Structured auto-fix suggestions for errors not handled by try_auto_fix
    suggestions = []
    if ret_code == 172 and message:
        suggestions.append("如果怀疑是 ProjectId 问题，请运行: call_api.py GetProjectList '{}' 确认项目列表。")
    if ret_code == 299:
        suggestions.append("RetCode 299 常见于缺少 ProjectId 而非真正的权限不足。请先确认 ProjectId 是否正确。")
    if re.search(r"not enough|insufficient|资源不足|售罄", message, re.I):
        suggestions.append("建议尝试: 1) 换可用区 2) 调小配置 3) 检查配额。")
    if re.search(r"stopped|关机", message, re.I):
        suggestions.append(f"建议执行: call_api.py Stop{action.replace('Resize','').replace('Reinstall','').replace('Reset','')} 先关机再重试。")

    if suggestions:
        print(f"\n{'='*50}")
        print("[Auto-Fix Suggestion] 可尝试的修复操作：")
        for s in suggestions:
            print(f"  → {s}")
        print("=" * 50)


def check_empty_result(result: dict, params: dict) -> None:
    """When a query returns empty and no ProjectId was specified, suggest cross-project scan."""
    if result.get("RetCode") != 0:
        return

    total = result.get("TotalCount", -1)
    has_project = "ProjectId" in params

    if total == 0 and not has_project:
        print(f"\n{'='*50}")
        print("[System Hint] 当前项目下未找到资源。")
        print("  建议使用 --all-projects 参数跨项目查询，或调用 GetProjectList 检查其他项目。")
        print("=" * 50)


# Account-level actions that never need Region/Zone/ProjectId — skip auto-fix for these.
ACCOUNT_LEVEL_ACTIONS = frozenset({
    "GetProjectList", "ListRegions", "ListZones", "GetBalance",
    "GetRegion", "DescribeChargeYear",
})


def _find_data_array(result: dict) -> list:
    """Extract the main data array from an API response."""
    for k, v in result.items():
        if isinstance(v, list) and k not in ("RetCode", "Message", "TotalCount", "Action"):
            return v
    return []


def try_auto_fix(action: str, params: dict, result: dict) -> dict | None:
    """Attempt to auto-fix common missing-parameter errors and retry.

    Auto-fix rules:
      1. Missing ProjectId → call GetProjectList.
         - Single project: fill in and retry silently.
         - Multiple projects: list them and let the user choose (no retry).
      2. Missing Region → call ListRegions, list options (no retry).
      3. Missing Zone  → call ListZones, list options (no retry).

    Returns the retried API result on successful auto-fix, or None if no fix was possible.
    """
    if action in ACCOUNT_LEVEL_ACTIONS:
        return None

    ret_code = result.get("RetCode", 0)
    message = result.get("Message", "")

    # ── 1. Missing ProjectId ──────────────────────────────────────────────
    # Triggers: RetCode 292 (project not found), 299 (IAM — often a missing
    # ProjectId rather than a real permission issue), 172 without ProjectId,
    # or RetCode 100 with "ProjectId" in the message.
    needs_project_fix = (
        ret_code == 292
        or (ret_code == 299 and "ProjectId" not in params)
        or (ret_code == 172 and "ProjectId" not in params)
        or (ret_code == 100 and re.search(r"ProjectId", message, re.I))
    )

    if needs_project_fix and "ProjectId" not in params:
        print(f"\n[Auto-Fix] 检测到可能缺少 ProjectId，正在查询项目列表...")
        proj_result = call_api("GetProjectList", {"Limit": 100})
        if proj_result.get("RetCode") == 0:
            projects = proj_result.get("ProjectSet", [])
            if len(projects) == 1:
                proj_id = projects[0]["ProjectId"]
                proj_name = projects[0].get("ProjectName", proj_id)
                print(f"[Auto-Fix] 发现唯一项目: {proj_name} ({proj_id})，自动补填并重试...")
                params["ProjectId"] = proj_id
                return call_api(action, params)
            elif len(projects) > 1:
                print(f"[Auto-Fix] 发现 {len(projects)} 个项目，请指定 ProjectId：")
                for p in projects:
                    print(f"  - {p.get('ProjectName', '?')} → {p['ProjectId']}")
                return None
        return None

    # ── 2. Missing Region ─────────────────────────────────────────────────
    if (ret_code == 100
            and re.search(r"Region", message, re.I)
            and "Region" not in params
            and not os.environ.get("UCLOUD_REGION")):
        print(f"\n[Auto-Fix] 检测到缺少 Region，正在查询可用地域...")
        region_result = call_api("ListRegions", {})
        if region_result.get("RetCode") == 0:
            regions = _find_data_array(region_result)
            if regions:
                print("[Auto-Fix] 可用地域：")
                for r in regions:
                    region_id = r.get("Region", "?")
                    region_name = r.get("RegionName", "")
                    print(f"  - {region_id}  {region_name}")
                print("[Auto-Fix] 请在参数中指定 Region 后重试。")
        return None

    # ── 3. Missing Zone ───────────────────────────────────────────────────
    if (ret_code == 100
            and re.search(r"Zone", message, re.I)
            and "Zone" not in params
            and not os.environ.get("UCLOUD_ZONE")):
        region = params.get("Region", os.environ.get("UCLOUD_REGION", ""))
        if region:
            print(f"\n[Auto-Fix] 检测到缺少 Zone，正在查询 {region} 的可用区...")
            zone_result = call_api("ListZones", {"Region": region})
            if zone_result.get("RetCode") == 0:
                zones = _find_data_array(zone_result)
                if zones:
                    print(f"[Auto-Fix] {region} 可用区：")
                    for z in zones:
                        zone_id = z.get("Zone", "?")
                        zone_name = z.get("ZoneName", "")
                        print(f"  - {zone_id}  {zone_name}")
                    print("[Auto-Fix] 请在参数中指定 Zone 后重试。")
        return None

    return None


def extract_fields(data, fields: list):
    """Extract specified fields from API response.

    Supports nested paths like "UHostSet.UHostId" and array traversal.
    When a field points to an array of objects, extracts the field from each element.

    Example:
        --fields UHostId,Name,State,IPSet
        Extracts those keys from each item in the top-level array (e.g., UHostSet).
    """
    if not fields:
        return data

    if not isinstance(data, dict):
        return data

    # Preserve RetCode and Message
    result = {}
    if "RetCode" in data:
        result["RetCode"] = data["RetCode"]
    if "Message" in data:
        result["Message"] = data["Message"]
    if "TotalCount" in data:
        result["TotalCount"] = data["TotalCount"]

    # Find the main data array (usually the largest list value)
    array_key = None
    for k, v in data.items():
        if isinstance(v, list) and k not in ("RetCode", "Message", "TotalCount", "Action"):
            if array_key is None or len(v) > len(data.get(array_key, [])):
                array_key = k

    if array_key and isinstance(data[array_key], list):
        filtered_items = []
        for item in data[array_key]:
            if isinstance(item, dict):
                filtered_items.append({f: item[f] for f in fields if f in item})
            else:
                filtered_items.append(item)
        result[array_key] = filtered_items
    else:
        # No array found, extract fields from top level
        for f in fields:
            if f in data:
                result[f] = data[f]

    return result


def run_all_projects(action: str, params: dict, fields: list) -> None:
    """Execute an action across all projects and aggregate results.

    1. Call GetProjectList to discover all projects
    2. For each project, call the target action with that ProjectId
    3. Aggregate and print results grouped by project
    """
    # Get all projects
    project_result = call_api("GetProjectList", {"Limit": 100})
    if project_result.get("RetCode") != 0:
        print(json.dumps({"error": f"GetProjectList failed: {project_result}"}, ensure_ascii=False, indent=2))
        return

    projects = project_result.get("ProjectSet", [])
    if not projects:
        print(json.dumps({"error": "No projects found"}, ensure_ascii=False, indent=2))
        return

    print(f"Scanning {len(projects)} projects...\n")

    # Query each project concurrently
    def query_project(project):
        proj_id = project["ProjectId"]
        proj_name = project.get("ProjectName", proj_id)
        p = dict(params)
        p["ProjectId"] = proj_id
        result = call_api(action, p)
        return proj_id, proj_name, result

    aggregated = []
    total_resources = 0

    with ThreadPoolExecutor(max_workers=min(len(projects), 10)) as executor:
        futures = {executor.submit(query_project, p): p for p in projects}
        for future in as_completed(futures):
            try:
                proj_id, proj_name, result = future.result()
            except Exception as e:
                proj = futures[future]
                aggregated.append({
                    "ProjectId": proj.get("ProjectId", "unknown"),
                    "ProjectName": proj.get("ProjectName", "unknown"),
                    "Error": str(e)
                })
                continue

            if result.get("RetCode") != 0:
                aggregated.append({
                    "ProjectId": proj_id,
                    "ProjectName": proj_name,
                    "Error": result.get("Message", f"RetCode: {result.get('RetCode')}")
                })
                continue

            # Apply field filtering
            if fields and result.get("RetCode") == 0:
                result = extract_fields(result, fields)

            count = result.get("TotalCount", 0)
            total_resources += count

            # Find the data array
            data_array = []
            for k, v in result.items():
                if isinstance(v, list) and k not in ("RetCode", "Message", "TotalCount", "Action"):
                    data_array = v
                    break

            if count > 0 or data_array:
                aggregated.append({
                    "ProjectId": proj_id,
                    "ProjectName": proj_name,
                    "TotalCount": count,
                    "Data": data_array
                })

    # Sort by ProjectName for consistent output
    aggregated.sort(key=lambda x: x.get("ProjectName", ""))

    output = {
        "Action": f"{action} (cross-project)",
        "TotalProjects": len(projects),
        "ProjectsWithResources": len([a for a in aggregated if a.get("TotalCount", 0) > 0]),
        "TotalResources": total_resources,
        "Results": aggregated
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


def main():
    if len(sys.argv) < 3:
        print(json.dumps({
            "error": "Usage: call_api.py <Action> '<json_params>' [--fields f1,f2,...] [--all-projects]"
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    action = sys.argv[1]

    # Safety gate: warn on delete-class operations
    if any(action.startswith(p) for p in DELETE_PREFIXES):
        print(f"\n{'='*50}")
        print(f"[Safety] {action} 是破坏性操作（不可逆）。")
        print(f"  即使用户说'不用确认'，也必须先展示资源详情并获得用户明确 YES。")
        print(f"  如果尚未确认，请立即中止并先向用户确认。")
        print(f"{'='*50}\n")

    try:
        params = json.loads(sys.argv[2])
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON params: {e}"}, ensure_ascii=False, indent=2))
        sys.exit(1)

    # Parse options
    fields = None
    all_projects = False

    for i, arg in enumerate(sys.argv[3:], 3):
        if arg == "--fields" and i + 1 < len(sys.argv):
            fields = [f.strip() for f in sys.argv[i + 1].split(",")]
        elif arg.startswith("--fields="):
            fields = [f.strip() for f in arg.split("=", 1)[1].split(",")]
        elif arg == "--all-projects":
            all_projects = True

    if all_projects:
        run_all_projects(action, params, fields)
    else:
        result = call_api(action, params)

        # Auto-fix: attempt to resolve missing ProjectId/Region/Zone
        if result.get("RetCode", 0) != 0:
            fixed = try_auto_fix(action, params, result)
            if fixed is not None:
                result = fixed

        # Error diagnosis
        if result.get("RetCode", 0) != 0:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            diagnose_error(result, action)
        else:
            if fields:
                result = extract_fields(result, fields)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            # Check for empty results
            check_empty_result(result, params)


if __name__ == "__main__":
    main()
