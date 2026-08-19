"""Factory for the one async Redis client type this codebase is allowed to
construct - same shape as `connection_factory.create_connection` for sqlite.
`redis.asyncio` (redis-py >= 4.2) is the async client; the old separate
`aioredis` package is stale and must not be used (Server_Design.md §12.2)."""

import redis.asyncio as redis


def create_redis_client(url: str) -> redis.Redis:
    return redis.from_url(url, decode_responses=True)
