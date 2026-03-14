#!/usr/bin/env python3
"""Route a user keyword to the matching UCloud product and list its APIs.

Product catalog is fetched from the official GitHub repo (apinav.json).
API lists come from per-product _sidebar.md files.
All data is cached locally for 24 hours.

Usage:
    python3 route_product.py <keyword>

Examples:
    python3 route_product.py 主机
    python3 route_product.py eip
    python3 route_product.py 物理机
"""

from __future__ import annotations

import json
import os
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Allow imports from scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from registry import build_product_registry, find_product, get_api_list


def load_product_hints() -> dict:
    """Load product-level SOP hints from hints/product_hints.json."""
    hints_path = os.path.join(SKILL_ROOT, "hints", "product_hints.json")
    if os.path.exists(hints_path):
        with open(hints_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.pop("_comment", None)
            return data
    return {}


def _match_hint_key(product_key: str, display_name: str, hints: dict) -> list | None:
    """Match a product to its hints using case-insensitive comparison.

    Hints keys are like "UHost", "UDB", "VPC". Product keys are like "uhost", "udb", "vpc".
    Also tries display_name for cases like display_name="UVPC" matching hints key "VPC".
    """
    for hint_key, hint_list in hints.items():
        hk = hint_key.lower()
        if hk == product_key or hk == display_name.lower():
            return hint_list
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: route_product.py <keyword>")
        sys.exit(1)

    keyword = sys.argv[1]
    registry = build_product_registry()
    matches = find_product(keyword, registry)

    if not matches:
        # Group products by category for easier browsing
        by_category: dict[str, list] = {}
        for key, info in sorted(registry.items()):
            cat = info.get("category", "其他")
            by_category.setdefault(cat, []).append(info)

        print(f"No product found for '{keyword}'.")
        print("Available products:")
        for cat, products in by_category.items():
            names = ", ".join(
                f"{p['display_name'] or p['key'].upper()} ({p['cname']})"
                for p in products
            )
            print(f"  [{cat}] {names}")
        sys.exit(0)

    if len(matches) > 1:
        print(f"Multiple matches found for '{keyword}':")
        for key, info in matches:
            display = info.get("display_name", "") or key.upper()
            cname = info.get("cname", "")
            print(f"  {display} ({cname}) — category: {info.get('category', '')}")
        print("Please clarify which product you mean.")
        sys.exit(0)

    # Single match
    key, info = matches[0]
    display_name = info.get("display_name", "") or key.upper()
    cname = info.get("cname", "")
    is_tier1 = "yes" if info.get("tier1") else "no"
    github_path = info["github_path"]

    print(f"Product: {display_name} ({cname})")
    print(f"Tier1: {is_tier1}")

    # Fetch API list from GitHub _sidebar.md (via registry cache)
    apis = get_api_list(github_path)

    if apis:
        print("APIs:")
        for api in apis:
            print(f"  {api['Name']} — {api.get('CName', '')}")
    else:
        print("APIs: (failed to fetch from GitHub, check network)")

    # Deterministic context injection: product-specific SOP hints
    product_hints = load_product_hints()
    hint_list = _match_hint_key(key, display_name, product_hints)
    if hint_list:
        print(f"\n{'='*50}")
        print(f"[System Hint] {display_name} 操作必读 SOP：")
        for i, hint in enumerate(hint_list, 1):
            print(f"  {i}. {hint}")
        print("=" * 50)
    else:
        print(f"\n{'='*50}")
        print("[System Hint] 通用提示：")
        print("  1. 执行写操作前，必须先调用 fetch_api_doc.py 获取完整参数文档。")
        print("  2. 如果必填参数涉及资源ID（如 ImageId, VPCId），先用对应的 Describe/List 接口查询，切勿凭空编造。")
        print("=" * 50)


if __name__ == "__main__":
    main()
