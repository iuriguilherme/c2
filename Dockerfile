FROM python:3.12-slim

WORKDIR /app

# Install build dependencies if needed, e.g. for redis or other C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first
COPY pyproject.toml requirements.txt ./

# Install dependencies using requirements.txt since that's what's currently in the repo
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything
COPY . .

# Install the application in non-editable mode
RUN pip install --no-cache-dir .
