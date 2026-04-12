FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies for C extensions (e.g., hiredis)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first
COPY pyproject.toml requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything and install the package without re-resolving dependencies
COPY . .
RUN pip install --no-cache-dir --no-deps .

FROM python:3.12-slim

WORKDIR /app

# Copy installed packages and scripts from builder (keeps build tools out of the runtime image)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source from builder
COPY --from=builder /app /app
