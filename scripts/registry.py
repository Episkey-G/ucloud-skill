"""Remote product registry built from UCloudDoc-Team/api on GitHub.

Replaces the local index.json with a runtime-generated registry.
Product catalog comes from apinav.json; API lists and URL paths come
from per-product _sidebar.md files.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

from cache import cached_fetch

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GITHUB_BASE = "https://raw.githubusercontent.com/UCloudDoc-Team/api/master"
APINAV_URL = f"{GITHUB_BASE}/apinav.json"

# Lazy-loaded singleton
_REGISTRY: dict | None = None


def _load_tier1() -> set:
    """Load tier1 product list from config/tier1.json."""
    path = os.path.join(SKILL_ROOT, "config", "tier1.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return {k.lower() for k in json.load(f)}
    return set()


def _extract_github_path(links: str) -> str:
    """Extract github_path from apinav links field.

    "/api/uhost-api/README" -> "uhost-api"
    "/api/ulb-api/index?id=alb" -> "ulb-api"
    """
    # Strip leading /api/ and trailing /README or /index...
    m = re.match(r"/api/([^/]+)", links)
    return m.group(1) if m else ""


def _parse_product_name(full_name: str) -> tuple[str, str, list[str]]:
    """Parse a product name from apinav.json into (cname, display_name, extra_terms).

    Examples:
        "云主机 UHost" -> ("云主机", "UHost", ["UHost"])
        "负载均衡 ULB ALB" -> ("负载均衡", "ULB", ["ULB", "ALB"])
        "云联网" -> ("云联网", "", [])
        "VPN网关 IPSec VPN" -> ("VPN网关", "IPSecVPN", ["IPSec", "VPN"])
        "云数据库 UDB MySQL" -> ("云数据库", "UDB", ["UDB", "MySQL"])
        "ES服务 ElasticSearch" -> ("ES服务", "ElasticSearch", ["ElasticSearch"])
    """
    # Split into Chinese prefix and English/product terms
    # Find the first English word (ASCII letter start)
    parts = full_name.split()
    chinese_parts = []
    english_parts = []
    hit_english = False
    for p in parts:
        if not hit_english and not re.match(r"[A-Za-z]", p):
            chinese_parts.append(p)
        else:
            hit_english = True
            english_parts.append(p)

    cname = " ".join(chinese_parts) if chinese_parts else full_name
    # Special: if cname contains parentheses like "（NVMe）", clean it
    cname = re.sub(r"[（(].*?[）)]", "", cname).strip()

    # display_name: first significant English term (product abbreviation)
    display_name = english_parts[0] if english_parts else ""
    extra_terms = english_parts[:]

    # Special handling: "公共 API" is not a useful product term
    extra_terms = [t for t in extra_terms if t not in ("公共", "API")]

    return cname, display_name, extra_terms


def _build_from_apinav(raw_json: str) -> dict:
    """Parse apinav.json and build the product registry.

    Returns dict keyed by github_path prefix (e.g., "uhost", "vpc").
    Multiple apinav entries sharing a github_path are merged (e.g., ULB ALB/CLB).
    """
    data = json.loads(raw_json)
    tier1_set = _load_tier1()
    registry = {}

    for category in data.get("api", []):
        cat_name = category.get("listname", "")
        for item in category.get("listvalue", []):
            full_name = item.get("name", "")
            links = item.get("links", "")
            if not links:
                continue

            github_path = _extract_github_path(links)
            if not github_path:
                continue

            key = github_path.replace("-api", "")
            cname, display_name, extra_terms = _parse_product_name(full_name)

            if key in registry:
                # Merge: add extra_terms from variant (e.g., ALB, CLB for ULB)
                existing = registry[key]
                for t in extra_terms:
                    if t not in existing["extra_terms"]:
                        existing["extra_terms"].append(t)
                # Keep the shortest/cleanest cname
                if len(cname) < len(existing["cname"]):
                    existing["cname"] = cname
            else:
                registry[key] = {
                    "key": key,
                    "display_name": display_name,
                    "cname": cname,
                    "full_name": full_name,
                    "github_path": github_path,
                    "category": cat_name,
                    "tier1": key in tier1_set,
                    "extra_terms": extra_terms,
                }

    return registry


def build_product_registry() -> dict:
    """Build or return cached product registry from remote apinav.json.

    Returns dict keyed by product key (e.g., "uhost", "vpc", "ulb").
    """
    global _REGISTRY
    if _REGISTRY is not None:
        return _REGISTRY

    raw = cached_fetch(APINAV_URL, "apinav.json")
    _REGISTRY = _build_from_apinav(raw)
    return _REGISTRY


def find_product(keyword: str, registry: dict | None = None) -> list:
    """Find matching products for a keyword using multi-level fuzzy matching.

    Priority:
        1. Exact key match (case-insensitive)
        2. Exact display_name / extra_terms match (case-insensitive)
        3. Exact cname match
        4. cname substring match
        5. extra_terms / key substring match

    Returns list of (product_key, info_dict) tuples.
    """
    if registry is None:
        registry = build_product_registry()

    kw = keyword.lower().strip()
    if not kw:
        return []

    # Level 1: exact key match
    if kw in registry:
        return [(kw, registry[kw])]

    # Level 2: exact display_name or extra_terms match
    for key, info in registry.items():
        names = [info["display_name"].lower()] + [t.lower() for t in info["extra_terms"]]
        if kw in names:
            return [(key, info)]

    # Level 3: exact cname match
    for key, info in registry.items():
        if kw == info["cname"]:
            return [(key, info)]

    # Level 4: cname substring match (bidirectional)
    matches = []
    for key, info in registry.items():
        cname = info["cname"]
        if kw in cname or cname in kw:
            matches.append((key, info))
    if matches:
        return matches

    # Level 5: key / display_name / extra_terms substring match
    for key, info in registry.items():
        searchable = [key] + [info["display_name"].lower()] + [t.lower() for t in info["extra_terms"]]
        searchable = [s for s in searchable if s]  # filter out empty strings
        for s in searchable:
            if kw in s or s in kw:
                matches.append((key, info))
                break
    if matches:
        return matches

    return []


def _fetch_sidebar(github_path: str) -> str:
    """Fetch _sidebar.md for a product with caching."""
    url = f"{GITHUB_BASE}/{github_path}/_sidebar.md"
    cache_key = f"{github_path}__sidebar.md"
    try:
        return cached_fetch(url, cache_key)
    except RuntimeError:
        return ""


def _parse_sidebar(content: str) -> list[dict]:
    """Parse _sidebar.md to extract API list.

    Lines like: - [中文名 - ActionName](api/product-api/snake_path)
    Returns list of {"Name": action, "CName": cname, "url_path": snake_path}.
    """
    apis = []
    # Match: - [CName - ActionName](api/product-api/snake_path)
    pattern = re.compile(r'^\s*-\s+\[(.+?)\s*-\s*(\w+)\]\(api/[^/]+/(\S+?)\)')
    for line in content.splitlines():
        m = pattern.match(line)
        if m:
            cname = m.group(1).strip()
            action = m.group(2).strip()
            url_path = m.group(3).strip()
            apis.append({"Name": action, "CName": cname, "url_path": url_path})
    return apis


def get_api_list(github_path: str) -> list[dict]:
    """Get the list of APIs for a product.

    Returns list of {"Name": "CreateUHostInstance", "CName": "创建云主机", "url_path": "create_uhost_instance"}.
    """
    content = _fetch_sidebar(github_path)
    return _parse_sidebar(content)


def get_action_url_path(github_path: str, action: str) -> str | None:
    """Look up the URL path for an action from the product's sidebar.

    Returns the snake_case path (e.g., "create_uhost_instance") or None.
    This eliminates the need for camel_to_snake conversion.
    """
    apis = get_api_list(github_path)
    for api in apis:
        if api["Name"] == action:
            return api["url_path"]
    return None


def get_github_path_for_action(action: str) -> str | None:
    """Reverse lookup: find which product owns a given action.

    Searches across all products' cached sidebars.
    Used by call_api.py for error code doc links.
    """
    registry = build_product_registry()
    for key, info in registry.items():
        apis = get_api_list(info["github_path"])
        for api in apis:
            if api["Name"] == action:
                return info["github_path"]
    return None
