import redis.asyncio as redis
import os
from dotenv import load_dotenv

load_dotenv()

shared_redis = redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379"),
    decode_responses=True
)