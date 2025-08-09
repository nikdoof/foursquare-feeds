# Build stage
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Result
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY generate_feeds.py ./
RUN mkdir -p /app/config && \
    useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
ENV PATH="/app/.venv/bin:$PATH"
USER app

# Set entrypoint with config file option
ENTRYPOINT ["python", "generate_feeds.py", "-c", "/app/config/config.ini"]
CMD ["--help"]
