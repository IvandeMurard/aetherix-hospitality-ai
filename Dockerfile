FROM python:3.11-slim

WORKDIR /app

# System deps for audio (sounddevice / scipy) and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    portaudio19-dev \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps (installed before COPY so layer is cached)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user — never run as root in production
RUN useradd -m -u 1000 appuser
COPY --chown=appuser:appuser . .
USER appuser

# Default: FastAPI
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
