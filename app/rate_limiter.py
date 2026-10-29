from dataclasses import dataclass
from pathlib import Path

import redis.asyncio as redis

SCRIPT_PATH = Path(__file__).parent / "scripts" / "token_bucket.lua"


@dataclass(frozen=True)
class Result:
    allowed: bool
    remaining: int
    retry_after_ms: int


class RateLimiter:
    """Token bucket backed by Redis; the check-and-decrement is one atomic Lua call."""

    def __init__(self, client: redis.Redis):
        # register_script uses EVALSHA and transparently loads the script if Redis lacks it
        self._script = client.register_script(SCRIPT_PATH.read_text())

    async def try_acquire(self, key: str, capacity: int, refill_per_sec: float) -> Result:
        try:
            allowed, remaining, retry_ms = await self._script(
                keys=[f"rl:{key}"], args=[capacity, refill_per_sec, 1]
            )
            return Result(allowed == 1, int(remaining), int(retry_ms))
        except Exception:
            # Fail-open: don't take the API down if Redis is unavailable
            return Result(True, -1, 0)
