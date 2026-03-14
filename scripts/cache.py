"""Unified HTTP fetch with disk cache, atomic write, and stale fallback.

All scripts share this module instead of each maintaining their own cache logic.
"""

import os
import tempfile
import time
import urllib.request
import urllib.error

CACHE_DIR = os.path.join("/tmp", "ucloud_skill_cache")
DEFAULT_TTL = 86400  # 24 hours


def cached_fetch(url: str, cache_key: str, ttl: int = DEFAULT_TTL) -> str:
    """Fetch URL content with disk cache.

    Args:
        url: The URL to fetch.
        cache_key: Unique key for the cache file (slashes replaced automatically).
        ttl: Cache time-to-live in seconds (default 24h).

    Returns:
        The fetched content as a string.

    On network failure, returns stale cache if available.
    Raises RuntimeError only when both network and cache fail.
    """
    safe_key = cache_key.replace("/", "_").replace("\\", "_")
    cache_path = os.path.join(CACHE_DIR, safe_key)

    # Check fresh cache
    if os.path.exists(cache_path):
        age = time.time() - os.path.getmtime(cache_path)
        if age < ttl:
            with open(cache_path, "r", encoding="utf-8") as f:
                return f.read()

    # Fetch from network
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ucloud-skill/2.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8")
        _atomic_write(cache_path, content)
        return content
    except Exception:
        # Stale fallback
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                return f.read()
        raise RuntimeError(f"Failed to fetch {url} and no cache available")


def _atomic_write(path: str, content: str) -> None:
    """Write content to path atomically via temp file + rename."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=CACHE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.rename(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
