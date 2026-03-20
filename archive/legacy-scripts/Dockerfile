# HuggingFace Space: API + Streamlit dashboard (single container).
# Exposes port 7860 = nginx reverse proxy. Routes API to FastAPI:8000, dashboard to Streamlit:8501.
FROM python:3.11-slim

WORKDIR /app

# Install nginx and curl (curl needed for proxy health checks)
RUN apt-get update && apt-get install -y nginx curl && rm -rf /var/lib/apt/lists/*

# Backend deps
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Frontend deps (Streamlit + requests, plotly, etc.)
COPY frontend/requirements.txt /app/frontend/requirements.txt
RUN pip install --no-cache-dir -r /app/frontend/requirements.txt

# App code (bump comment below to force no-cache for frontend on HF)
# Frontend copy: 2026-02-09 (updated with improved error handling, UI improvements, and Streamlit Cloud detection)
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY scripts/start_app_with_dashboard.sh /app/scripts/

# Copy nginx config (backup option)
COPY nginx.conf /etc/nginx/nginx.conf

# Copy Python proxy script (alternative to nginx)
COPY scripts/start_app_with_proxy.py /app/scripts/

ENV DISABLE_FILE_LOGGING=true
ENV AETHERIX_API_BASE=http://localhost:8000
# Visible in sidebar to confirm deployed build (update when pushing UI changes)
ENV AETHERIX_BUILD=2026-02-09-python-proxy-fix

EXPOSE 7860

RUN chmod +x /app/scripts/start_app_with_dashboard.sh && \
    chmod +x /app/scripts/start_app_with_proxy.py
# Use nginx reverse proxy (WebSocket support, reliable routing)
CMD ["/app/scripts/start_app_with_dashboard.sh"]
