# OS AI Backend — production image.
# Slim base, non-root user, writable data dir for the bot/live ledgers.
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Never run as root in production. Pre-create the data dir so the named
# volume inherits appuser ownership (ledgers + tuning overrides live there).
RUN useradd --create-home appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
