"""In-memory sliding-window rate limiter and security headers middleware."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window rate limiter keyed by (client_ip, route_prefix)."""

    def __init__(self, window_seconds: int = 60) -> None:
        self.window_seconds = window_seconds
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: tuple[str, str], limit: int, now: float | None = None) -> tuple[bool, int]:
        if limit <= 0:
            return True, 0
        ts = time.monotonic() if now is None else now
        cutoff = ts - self.window_seconds
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(bucket[0] + self.window_seconds - ts) + 1)
                return False, retry_after
            bucket.append(ts)
            return True, 0


class SecurityAndRateLimitMiddleware(BaseHTTPMiddleware):
    """Applies rate limits on sensitive endpoints and adds HTTP security headers."""

    def __init__(
        self,
        app: ASGIApp,
        api_prefix: str = "/api/v1",
        login_limit_per_min: int = 20,
        assistant_limit_per_min: int = 30,
    ) -> None:
        super().__init__(app)
        self.limiter = SlidingWindowRateLimiter(window_seconds=60)
        self.limits: dict[str, int] = {
            f"{api_prefix}/auth/login": login_limit_per_min,
            f"{api_prefix}/assistant/ask": assistant_limit_per_min,
        }
        self.api_prefix = api_prefix

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        limit = self.limits.get(path)
        if limit is not None and request.method == "POST":
            client_ip = request.client.host if request.client else "unknown"
            allowed, retry_after = self.limiter.allow((client_ip, path), limit)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "rate_limit_exceeded",
                            "message": "Przekroczono limit zapytań. Spróbuj ponownie za chwilę.",
                        }
                    },
                    headers={"Retry-After": str(retry_after)},
                )

        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if path.startswith(self.api_prefix):
            response.headers.setdefault("Cache-Control", "no-store")
        return response
