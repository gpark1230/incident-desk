import json
import logging
from datetime import datetime, timezone

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from app.config import REDIS_URL

logger = logging.getLogger(__name__)

INCIDENT_EVENTS_KEY = "incident_events"

# redis-py connects lazily (on the first real command), so constructing this
# client at import time is safe even if Redis is down -- same spirit as
# SQLAlchemy's engine in app/database.py. Short timeouts so an unreachable
# Redis fails fast instead of stalling a request (or the test suite).
#
# retry=Retry(NoBackoff(), 0) is NOT optional here: redis-py 5.x+ defaults to
# retrying connection errors 10 times with exponential backoff, regardless of
# socket_connect_timeout -- a single unreachable-Redis call took ~9.5s before
# this was set explicitly, since the socket timeout only bounds one attempt,
# not the whole retry loop. This is meant to fail once, fast, and move on.
_client = redis.Redis.from_url(
    REDIS_URL,
    socket_connect_timeout=1,
    socket_timeout=1,
    retry=Retry(NoBackoff(), 0),
    retry_on_error=[],
)


def publish_event(event: str, incident_id: int, user_id: int, details: str | None = None) -> None:
    """Publishes a small JSON event to a Redis list, right alongside the audit log write.

    Best-effort only. Redis is optional infrastructure -- this must never be
    the reason an incident/comment request fails, so any failure (Redis down,
    a network blip, whatever) is logged as a warning and swallowed here.
    """
    payload = {
        "event": event,
        "incident_id": incident_id,
        "user_id": user_id,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        _client.rpush(INCIDENT_EVENTS_KEY, json.dumps(payload))
    except Exception as exc:  # deliberately broad -- see docstring
        logger.warning("Could not publish incident event to Redis: %s", exc)
