-- KEYS[1] = bucket key
-- ARGV[1] = capacity, ARGV[2] = refill tokens/sec, ARGV[3] = tokens requested
local t = redis.call('TIME')
local now = t[1] * 1000 + math.floor(t[2] / 1000)   -- ms, Redis clock (no app-server skew)

local capacity = tonumber(ARGV[1])
local rate     = tonumber(ARGV[2])
local requested = tonumber(ARGV[3])

local data   = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(data[1]) or capacity
local ts     = tonumber(data[2]) or now

tokens = math.min(capacity, tokens + (math.max(0, now - ts) / 1000) * rate)

local allowed = 0
if tokens >= requested then
  tokens = tokens - requested
  allowed = 1
end

redis.call('HSET', KEYS[1], 'tokens', tokens, 'ts', now)
redis.call('PEXPIRE', KEYS[1], math.ceil(capacity / rate * 1000) * 2)

local retryAfterMs = 0
if allowed == 0 then
  retryAfterMs = math.ceil((requested - tokens) / rate * 1000)
end
return { allowed, math.floor(tokens), retryAfterMs }
