import hashlib
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if settings.rate_limit_enabled and request.url.path.startswith("/api/v1"):
            host = request.client.host if request.client else "unknown"
            identity = hashlib.sha256(host.encode()).hexdigest()
            key = f"uploadio:limit:{identity}:{int(time.time() // 60)}"
            try:
                async with Redis.from_url(
                    settings.redis_url, socket_connect_timeout=2, socket_timeout=2
                ) as redis:
                    script = (
                        "local n=redis.call('INCR',KEYS[1]); "
                        "if n==1 then redis.call('EXPIRE',KEYS[1],65) end; return n"
                    )
                    count = await redis.eval(script, 1, key)
                if count > 120:
                    return JSONResponse(
                        {"detail": "Too many requests; try again shortly"},
                        status_code=429,
                        headers={"Retry-After": "60"},
                    )
            except RedisError:
                return JSONResponse(
                    {"detail": "Request service temporarily unavailable"}, status_code=503
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        return response
