import time
from collections import defaultdict

from fastapi import Depends, HTTPException

from src.api.auth import get_api_key
from src.db.models import ApiKey

TIER_LIMITS = {
    "free": 30,
    "individual": 100,
    "team": 500,
}
DEFAULT_LIMIT = 30
WINDOW_SECONDS = 60

# key -> list of request timestamps
_request_log: dict[str, list[float]] = defaultdict(list)


def rate_limit(api_key: ApiKey = Depends(get_api_key)) -> ApiKey:
    now = time.monotonic()
    window_start = now - WINDOW_SECONDS
    log = _request_log[api_key.key]

    # Drop timestamps outside the window
    _request_log[api_key.key] = [t for t in log if t > window_start]
    log = _request_log[api_key.key]

    max_requests = TIER_LIMITS.get(api_key.tier, DEFAULT_LIMIT)
    if len(log) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({max_requests} requests/minute)",
        )

    log.append(now)
    return api_key
