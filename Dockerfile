FROM python:3.11-slim

WORKDIR /app

# Install deps first, separately from the app code, so Docker's layer cache
# only reinstalls packages when requirements.txt actually changes -- not on
# every code edit.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Same as the Procfile: run pending migrations before the server starts,
# never at import time inside the app itself. $PORT falls back to 8000 for
# plain `docker run` (Railway injects its own $PORT at runtime).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
