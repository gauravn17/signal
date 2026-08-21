import redis
from rq import Queue

from signal_backend.config import settings


def get_redis_connection() -> redis.Redis:
    return redis.from_url(settings.redis_url)


def get_stage2_queue() -> Queue:
    return Queue("stage2", connection=get_redis_connection())
