#!/usr/bin/env python3
"""Fetch an API's documentation from GitHub and inject prerequisite hints.

Instead of reading local JSON files, fetches the official API doc from
UCloudDoc-Team/api on GitHub. The model reads the Markdown table directly
— no parsing needed.

Usage:
    python3 fetch_api_doc.py <product> <ActionName>

Examples:
    python3 fetch_api_doc.py UHost CreateUHostInstance
    python3 fetch_api_doc.py UDB DescribeUDBInstance

Output:
    [System Hint] block (if hints exist for this API)
    + raw Markdown from GitHub (parameter tables, examples, etc.)
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GITHUB_BASE = "https://raw.githubusercontent.com/UCloudDoc-Team/api/master"
CACHE_DIR = os.path.join("/tmp", "ucloud_skill_cache")
CACHE_TTL = 3600  # 1 hour

# UCloud product abbreviations that should stay as one unit in snake_case conversion.
# E.g., "UHost" → "uhost" (not "u_host"), "EIP" → "eip" (not "e_i_p").
_PRODUCT_ABBREVS = [
    'UHost', 'UDisk', 'UNet', 'UDB', 'ULB', 'UMem', 'UFile', 'UCDN',
    'UPHost', 'UPhone', 'UK8S', 'UEC', 'UFS', 'UGN', 'UDDB', 'UDTS',
    'UHub', 'UDPN', 'UDI', 'USLK', 'UNVS', 'UPFS', 'UAAA', 'UDBProxy',
    'EIP', 'VPC', 'IAM', 'STS', 'PHost', 'PathX', 'TiDB',
]


def load_api_hints() -> dict:
    """Load API-level prerequisite hints from hints/api_hints.json."""
    hints_path = os.path.join(SKILL_ROOT, "hints", "api_hints.json")
    if os.path.exists(hints_path):
        with open(hints_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.pop("_comment", None)
            return data
    return {}


def load_index() -> dict:
    """Load the product index."""
    index_path = os.path.join(SKILL_ROOT, "apis", "index.json")
    with open(index_path, "r", encoding="utf-8") as f:
        return json.load(f)


def camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case for GitHub URL.

    Preserves UCloud product abbreviations as single units:
        CreateUHostInstance -> create_uhost_instance
        DescribeEIP -> describe_eip
        GetUHostInstancePrice -> get_uhost_instance_price
    """
    # Protect known product abbreviations by lowercasing them as units
    for abbrev in sorted(_PRODUCT_ABBREVS, key=len, reverse=True):
        name = name.replace(abbrev, '_' + abbrev.lower() + '_')
    # Clean up: collapse multiple underscores, strip leading/trailing
    name = re.sub(r'_+', '_', name).strip('_')
    # Handle remaining CamelCase transitions
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name)
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', s)
    return s.lower()


def fetch_doc(github_path: str, action_snake: str) -> str:
    """Fetch API doc from GitHub with local disk cache. Returns markdown content or error message."""
    url = f"{GITHUB_BASE}/{github_path}/{action_snake}.md"
    cache_key = f"{github_path}_{action_snake}.md".replace("/", "_")
    cache_path = os.path.join(CACHE_DIR, cache_key)

    # Check cache
    if os.path.exists(cache_path):
        age = time.time() - os.path.getmtime(cache_path)
        if age < CACHE_TTL:
            with open(cache_path, "r", encoding="utf-8") as f:
                return f.read()

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ucloud-skill/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8")
        # Write cache
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(content)
        return content
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"ERROR: Document not found at {url}\nThe action name might be wrong. Check the API list from route_product.py."
        return f"ERROR: HTTP {e.code} fetching {url}: {e.reason}"
    except Exception as e:
        # On network failure, try stale cache as fallback
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                return f.read()
        return f"ERROR: Failed to fetch {url}: {e}"


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <Product> <ActionName>")
        print(f"Example: {sys.argv[0]} UHost CreateUHostInstance")
        sys.exit(1)

    product = sys.argv[1]
    action = sys.argv[2]

    # Look up product in index
    index = load_index()
    product_info = index.get(product)
    if not product_info:
        # Try case-insensitive match
        for k, v in index.items():
            if k.lower() == product.lower():
                product = k
                product_info = v
                break

    if not product_info:
        print(f"ERROR: Product '{product}' not found in index.")
        print(f"Available: {', '.join(sorted(index.keys()))}")
        sys.exit(1)

    github_path = product_info["github_path"]
    action_snake = camel_to_snake(action)

    # === Deterministic context injection: API-level hints ===
    api_hints = load_api_hints()
    hints = api_hints.get(action, [])

    if hints:
        print("=" * 50)
        print(f"[System Hint] {action} 前置操作：")
        for h in hints:
            print(f"  ⚠ {h}")
        print("=" * 50)
        print()

    # Fetch and output the doc
    print(f"Source: {GITHUB_BASE}/{github_path}/{action_snake}.md")
    print()
    content = fetch_doc(github_path, action_snake)
    print(content)

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
