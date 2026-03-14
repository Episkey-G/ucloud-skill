#!/usr/bin/env python3
"""Fetch an API's documentation from GitHub and inject prerequisite hints.

Uses the remote registry to look up the product's github_path and the
exact URL path from _sidebar.md — no camelCase-to-snake_case conversion needed.

Usage:
    python3 fetch_api_doc.py <product> <ActionName>

Examples:
    python3 fetch_api_doc.py UHost CreateUHostInstance
    python3 fetch_api_doc.py UDB DescribeUDBInstance

Output:
    [System Hint] block (if hints exist for this API)
    + raw Markdown from GitHub (parameter tables, examples, etc.)
"""

from __future__ import annotations

import json
import os
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GITHUB_BASE = "https://raw.githubusercontent.com/UCloudDoc-Team/api/master"

# Allow imports from scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cache import cached_fetch
from registry import build_product_registry, get_action_url_path


# API action prefix classification (CRUD)
# fmt: off
DELETE_PREFIXES = [
    "Terminate", "Remove", "Unpublish", "Cancel", "Abort", "Del",
    "Unassign", "Release", "Destroy", "Delete",
]
# fmt: on


def load_api_hints() -> dict:
    """Load API-level prerequisite hints from hints/api_hints.json."""
    hints_path = os.path.join(SKILL_ROOT, "hints", "api_hints.json")
    if os.path.exists(hints_path):
        with open(hints_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Remove metadata keys
            for k in list(data):
                if k.startswith("_"):
                    data.pop(k)
            return data
    return {}


def is_delete_action(action: str) -> bool:
    """Check if an action is a delete operation based on its prefix."""
    return any(action.startswith(p) for p in DELETE_PREFIXES)


def get_destructive_hints(action: str) -> list:
    """Return forced-confirmation hints for delete operations."""
    for prefix in DELETE_PREFIXES:
        if action.startswith(prefix):
            return [
                f"🚨 破坏性操作（{prefix}*）！此操作不可逆，即使用户明确说'不用确认'也必须强制确认。",
                "执行前必须：1) 调用 Describe* 获取资源详情 → 2) 展示给用户 → 3) 等待用户明确回复 YES。"
            ]
    return []


def _find_product_info(product: str, registry: dict) -> tuple[str, dict] | None:
    """Find product info by name, case-insensitive.

    Searches registry keys and display_names.
    """
    product_lower = product.lower()
    for key, info in registry.items():
        if key == product_lower:
            return key, info
        if info.get("display_name", "").lower() == product_lower:
            return key, info
        # Also check extra_terms for cases like "EIP" → UNet
        for term in info.get("extra_terms", []):
            if term.lower() == product_lower:
                return key, info
    return None


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <Product> <ActionName>")
        print(f"Example: {sys.argv[0]} UHost CreateUHostInstance")
        sys.exit(1)

    product = sys.argv[1]
    action = sys.argv[2]

    # Look up product in registry
    registry = build_product_registry()
    result = _find_product_info(product, registry)

    if not result:
        available = ", ".join(
            info.get("display_name", "") or key.upper()
            for key, info in sorted(registry.items())
        )
        print(f"ERROR: Product '{product}' not found in registry.")
        print(f"Available: {available}")
        sys.exit(1)

    key, product_info = result
    github_path = product_info["github_path"]

    # Get the exact URL path from _sidebar.md (no camel_to_snake needed)
    action_path = get_action_url_path(github_path, action)
    if not action_path:
        print(f"WARNING: Action '{action}' not found in {github_path}/_sidebar.md.")
        print(f"Falling back to lowercase action name.")
        action_path = action.lower()

    # === Deterministic context injection: API-level hints ===
    api_hints = load_api_hints()
    # First, get specific hints for this action
    hints = list(api_hints.get(action, []))
    # Then, add destructive operation hints based on prefix matching
    destructive_hints = get_destructive_hints(action)
    for dh in destructive_hints:
        if dh not in hints:
            hints.append(dh)

    if hints:
        print("=" * 50)
        print(f"[System Hint] {action} 前置操作：")
        for h in hints:
            print(f"  ⚠ {h}")
        print("=" * 50)
        print()

    # Fetch and output the doc
    url = f"{GITHUB_BASE}/{github_path}/{action_path}.md"
    print(f"Source: {url}")
    print()

    try:
        content = cached_fetch(url, f"{github_path}_{action_path}.md")
        print(content)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # === Call template: show ready-to-use command ===
    print()
    print("=" * 50)
    print(f"[Call Template] call_api.py 调用格式：")
    print()
    print(f"  python3 <skill-path>/scripts/call_api.py {action} '<json_params>'")
    print()
    print("  签名自动计算（读取 UCLOUD_PUBLIC_KEY / UCLOUD_PRIVATE_KEY 环境变量），无需手动处理。")
    print()
    print("  参数格式说明：")
    print("  - 普通参数: {\"Region\":\"cn-bj2\", \"CPU\":2, \"Memory\":4096}")
    print("  - 数组参数 (如 Disks.N.xx): 传 JSON 数组，脚本自动展平为 Dot.N.Key 格式")
    print("    示例: \"Disks\":[{\"IsBoot\":\"True\",\"Type\":\"CLOUD_SSD\",\"Size\":40}]")
    print("    → 自动展平为 Disks.0.IsBoot=True, Disks.0.Type=CLOUD_SSD, Disks.0.Size=40")
    print("  - 嵌套数组 (如 Network): 传 JSON 数组")
    print("    示例: \"Network\":[\"10.0.0.0/16\"]")
    print("    → 自动展平为 Network.0=10.0.0.0/16")
    print("  - Boolean: 使用字符串 \"True\"/\"False\"")
    print("=" * 50)


if __name__ == "__main__":
    main()
