#!/usr/bin/env python3
"""Route a user keyword to the matching UCloud product and list its APIs.

Merges Step 1 (identify product) and Step 2 (list APIs) into a single script
call, so the model doesn't need to read index.json or summary files.

Usage:
    python3 route_product.py <keyword> [--api-dir <path>]

Examples:
    python3 route_product.py 主机
    python3 route_product.py eip
    python3 route_product.py 物理机
    python3 route_product.py redis --api-dir ../apis

Output on match:
    Product: UHost
    File: uhost.json
    Tier1: yes
    APIs:
      CreateUHostInstance — 创建云主机
      DescribeUHostInstance — 获取主机信息
      ...

Output on ambiguous match:
    Multiple matches found for '主机':
      UHost (云主机): 主机, 云主机, 服务器, 虚拟机, 机器
      UPHost (裸金属云主机): 物理机, 裸金属
    Please clarify which product you mean.

Output on no match:
    No product found for 'xxx'.
    Available products: UHost, UDisk, UNet, ...
"""

import json
import os
import sys

TIER1_PRODUCTS = {"UHost", "UDisk", "UNet", "VPC", "ULB", "UDB"}

# Skill root directory (for loading hints/)
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_product_hints() -> dict:
    """Load product-level SOP hints from hints/product_hints.json."""
    hints_path = os.path.join(SKILL_ROOT, "hints", "product_hints.json")
    if os.path.exists(hints_path):
        with open(hints_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.pop("_comment", None)
            return data
    return {}

# Product Chinese names (for display only, not stored in index)
PRODUCT_CNAMES = {
    "UHost": "云主机", "UDisk": "云硬盘", "UNet": "基础网络",
    "VPC": "私有网络", "ULB": "负载均衡", "UDB": "云数据库 MySQL",
    "UMem": "云内存", "UFile": "对象存储", "UCDN": "云分发",
    "UPHost": "裸金属云主机", "UPhone": "云手机", "UK8S": "容器云",
    "IAM": "访问控制", "PathX": "全球动态加速",
    "UPgSQL": "云数据库 PostgreSQL", "UMongoDB": "云数据库 MongoDB",
    "USMS": "短信服务", "IPSecVPN": "VPN网关", "UAccount": "账号管理",
    "UBill": "账单管理", "UDNS": "云解析", "UFS": "文件存储",
    "UEC": "边缘计算虚拟机", "UCompShare": "轻量算力平台",
    "UGN": "云联网", "UDDB": "分布式数据库", "UDTS": "数据传输服务",
    "UHub": "容器镜像库", "Cube": "容器实例", "UTSDB": "时序数据库",
    "UPFS": "文件存储", "UDPN": "高速通道", "UDI": "数据智能",
    "USLK": "短链工具", "TiDB": "TiDB服务", "UNVS": "网络增值服务",
    "StepFlow": "工作流服务", "UVMS": "语音消息服务",
    "STS": "安全令牌服务", "UDBProxy": "数据库读写分离中间件",
    "ISMS": "视频短信", "UAI_Modelverse": "模型服务平台",
    "UAAA": "应用仓库加速",
}


def find_product(keyword: str, index: dict) -> list:
    """Find matching products for a keyword. Returns list of (product_name, info) tuples."""
    keyword_lower = keyword.lower()
    matches = []

    for product, info in index.items():
        # Exact product name match (case-insensitive)
        if keyword_lower == product.lower():
            matches.append((product, info))
            continue

        # Alias match
        for alias in info.get("aliases", []):
            if keyword_lower == alias.lower() or keyword_lower in alias.lower():
                matches.append((product, info))
                break

    return matches


def main():
    if len(sys.argv) < 2:
        print("Usage: route_product.py <keyword> [--api-dir <path>]")
        sys.exit(1)

    keyword = sys.argv[1]

    # Parse --api-dir
    api_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "apis")
    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == "--api-dir" and i + 1 < len(sys.argv):
            api_dir = sys.argv[i + 1]
            break

    # Load index
    index_path = os.path.join(api_dir, "index.json")
    if not os.path.exists(index_path):
        print(f"Error: index.json not found at {index_path}")
        sys.exit(1)

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    matches = find_product(keyword, index)

    if not matches:
        products = ", ".join(sorted(index.keys()))
        print(f"No product found for '{keyword}'.")
        print(f"Available products: {products}")
        sys.exit(0)

    if len(matches) > 1:
        print(f"Multiple matches found for '{keyword}':")
        for product, info in matches:
            cname = PRODUCT_CNAMES.get(product, "")
            aliases = ", ".join(info.get("aliases", []))
            print(f"  {product} ({cname}): {aliases}")
        print("Please clarify which product you mean.")
        sys.exit(0)

    # Single match — output product info + API list
    product, info = matches[0]
    cname = PRODUCT_CNAMES.get(product, "")
    is_tier1 = "yes" if product in TIER1_PRODUCTS else "no"

    print(f"Product: {product} ({cname})")
    print(f"Tier1: {is_tier1}")

    # Read API list from merged index (no more separate summary files)
    apis = info.get("apis", [])
    if apis:
        print("APIs:")
        for api in apis:
            print(f"  {api['Name']} — {api.get('CName', '')}")

    # Deterministic context injection: product-specific SOP hints
    product_hints = load_product_hints()
    hints = product_hints.get(product)
    if hints:
        print(f"\n{'='*50}")
        print(f"[System Hint] {product} 操作必读 SOP：")
        for i, hint in enumerate(hints, 1):
            print(f"  {i}. {hint}")
        print("=" * 50)
    else:
        # Generic fallback for unconfigured products
        print(f"\n{'='*50}")
        print("[System Hint] 通用提示：")
        print("  1. 执行写操作前，必须先调用 fetch_api_doc.py 获取完整参数文档。")
        print("  2. 如果必填参数涉及资源ID（如 ImageId, VPCId），先用对应的 Describe/List 接口查询，切勿凭空编造。")
        print("=" * 50)


if __name__ == "__main__":
    main()
