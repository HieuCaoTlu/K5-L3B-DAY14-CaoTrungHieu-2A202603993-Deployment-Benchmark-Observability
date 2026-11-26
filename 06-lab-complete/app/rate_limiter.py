"""Rate limiting: sliding window 60s bằng Redis sorted set, vượt → 429 + Retry-After."""
import hashlib
import time
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    # Băm API key để không lưu key thật trong Redis
    rkey = "ratelimit:" + hashlib.sha256(key.encode()).hexdigest()[:16]
    now = time.time()
    pipe = r.pipeline()
    pipe.zremrangebyscore(rkey, 0, now - WINDOW_SECONDS)
    pipe.zcard(rkey)
    _, count = pipe.execute()

    limit = settings.rate_limit_per_minute
    if count >= limit:
        oldest = r.zrange(rkey, 0, 0, withscores=True)
        retry_after = int(oldest[0][1] + WINDOW_SECONDS - now) + 1 if oldest else WINDOW_SECONDS
        raise HTTPException(status_code=429, detail="Rate limit exceeded",
                            headers={"Retry-After": str(max(retry_after, 1)),
                                     "X-RateLimit-Limit": str(limit)})

    pipe = r.pipeline()
    pipe.zadd(rkey, {f"{now}-{uuid.uuid4().hex[:8]}": now})
    pipe.expire(rkey, WINDOW_SECONDS)
    pipe.execute()
