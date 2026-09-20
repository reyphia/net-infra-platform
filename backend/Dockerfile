FROM python:3.11-slim AS base

# iproute2 gives the discovery engine a real `ip neighbor` command; iputils-ping
# provides `ping` for ICMP probing. Both are genuine runtime dependencies of
# app/discovery, not build-time extras.
RUN apt-get update && apt-get install -y --no-install-recommends \
    iproute2 \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

RUN mkdir -p /app/data/backups

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
