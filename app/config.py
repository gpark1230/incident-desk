import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
SECRET_KEY = os.environ["SECRET_KEY"]

# Optional infra, unlike the two above: the app must keep working if Redis is
# unreachable (event publishing degrades gracefully, see app/events.py), so
# this uses .get() with a local-dev default instead of the fail-fast
# os.environ[...] pattern used for DATABASE_URL/SECRET_KEY.
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
