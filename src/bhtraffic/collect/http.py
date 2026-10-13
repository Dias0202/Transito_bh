"""Tiny stdlib HTTP helper so the collector needs no third-party packages."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from bhtraffic.config import HTTP_USER_AGENT


def get(url: str, params: dict | None = None, timeout: float = 20, retries: int = 2) -> bytes:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": HTTP_USER_AGENT})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            # 4xx other than rate limiting will not get better on retry.
            if (e.code != 429 and e.code < 500) or attempt == retries:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries:
                raise
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def get_json(url: str, params: dict | None = None, **kw) -> dict:
    return json.loads(get(url, params, **kw))
