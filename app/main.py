import math
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis.asyncio as redis
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .rate_limiter import RateLimiter

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CAPACITY = int(os.getenv("RATELIMIT_CAPACITY", "10"))          # max burst
REFILL_PER_SEC = float(os.getenv("RATELIMIT_REFILL", "2"))      # sustained rate
EXCLUDED_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc")


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = redis.from_url(REDIS_URL, socket_timeout=0.2, socket_connect_timeout=0.2)
    app.state.redis = client
    app.state.limiter = RateLimiter(client)
    yield
    await client.aclose()


app = FastAPI(title="Redis rate limit demo", lifespan=lifespan)


def client_key(request: Request) -> str:
    api_key = request.headers.get("x-api-key")
    if api_key:
        return f"key:{api_key}"
    # Behind a proxy, run uvicorn with --proxy-headers so this is the real client IP
    return f"ip:{request.client.host if request.client else 'unknown'}"


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path.startswith(EXCLUDED_PREFIXES):
        return await call_next(request)

    result = await request.app.state.limiter.try_acquire(
        client_key(request), CAPACITY, REFILL_PER_SEC
    )
    headers = {"X-RateLimit-Limit": str(CAPACITY)}
    if result.remaining >= 0:
        headers["X-RateLimit-Remaining"] = str(result.remaining)

    if not result.allowed:
        headers["Retry-After"] = str(max(1, math.ceil(result.retry_after_ms / 1000)))
        return JSONResponse({"error": "rate_limit_exceeded"}, status_code=429, headers=headers)

    response = await call_next(request)
    response.headers.update(headers)
    return response


@app.get("/api/hello")
async def hello():
    return {"message": "hello", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/health")
async def health():
    return {"status": "ok"}
