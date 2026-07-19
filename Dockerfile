FROM python:3.12-slim

# Install system dependencies (ffmpeg for video stitching)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    git \
    fonts-dejavu-core \
    fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy pyproject.toml and lock file
COPY pyproject.toml .

# Install dependencies using uv
RUN uv pip install --system -r pyproject.toml

# Copy source code and static assets
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV PYTHONPATH=/app/src

EXPOSE 8080

# Run FastAPI production server
CMD ["uvicorn", "src.omnimash.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
