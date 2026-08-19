import redis.asyncio as redis

from server.infrastructure.redis_client import create_redis_client


class TestCreateRedisClient:
    def test_returns_an_async_redis_client(self):
        # from_url() builds the client without opening a connection, so this
        # is safe to assert without a live Redis server.
        client = create_redis_client("redis://127.0.0.1:6379")
        assert isinstance(client, redis.Redis)
