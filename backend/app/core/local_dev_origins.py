"""`app_env=local` 에서 같은 내부망 PC(예: 옆 자리)가 Vite(5173)로 접근할 때 CORS·CSRF·OAuth 허용용."""

from __future__ import annotations

import re
from urllib.parse import urlparse

# 사설 대역·localhost만, http 고정·포트는 Vite dev 기본값
LAN_VITE_ORIGIN_REGEX = (
    r"^http://(?:127\.0\.0\.1|localhost|"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}):5173$"
)

LAN_VITE_ORIGIN_RE = re.compile(LAN_VITE_ORIGIN_REGEX)


def is_local_lan_vite_origin(origin: str | None, referer: str | None) -> bool:
    """Origin 또는 Referer의 scheme://host:port 가 로컬 dev Vite 패턴과 맞는지."""
    if origin and LAN_VITE_ORIGIN_RE.match(origin.strip()):
        return True
    if referer and referer.strip():
        p = urlparse(referer.strip())
        if p.scheme and p.netloc:
            cand = f"{p.scheme}://{p.netloc}"
            return bool(LAN_VITE_ORIGIN_RE.match(cand))
    return False

