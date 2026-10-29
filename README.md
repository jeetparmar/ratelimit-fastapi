# Redis rate limiting demo (FastAPI)

Token-bucket limiter backed by Redis (atomic Lua script), applied to all requests via HTTP middleware.

## Run
```bash
docker compose up --build
./test.sh
```
Expected: ~10 x `200` (burst), then `429` until tokens refill (2/sec). Docs at http://localhost:8000/docs

## Config (env vars)
- `REDIS_URL` (default `redis://localhost:6379/0`)
- `RATELIMIT_CAPACITY` max burst (default 10)
- `RATELIMIT_REFILL` tokens/sec (default 2)

Clients are keyed by `X-API-Key` header, else by IP:
```bash
curl -i -H "X-API-Key: alice" localhost:8000/api/hello
```

## Local dev
```bash
docker compose up redis -d
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Layout
- `app/main.py` - FastAPI app, middleware, routes
- `app/rate_limiter.py` - loads/runs `scripts/token_bucket.lua`; fails open if Redis is down
- `app/scripts/token_bucket.lua` - atomic token bucket
