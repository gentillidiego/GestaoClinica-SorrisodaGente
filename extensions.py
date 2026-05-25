import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

limiter = Limiter(
    get_remote_address,
    default_limits=["5000 per day", "500 per hour"],
    storage_uri=REDIS_URL
)

cache = Cache()
