# HuggingFace Space: API + Streamlit dashboard (single container).
# Exposes port 7860 = dashboard. API runs on 8000 inside container; dashboard calls it via localhost.
FROM python:3.11-slim

WORKDIR /app

# Backend deps
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Frontend deps (Streamlit + requests, plotly, etc.)
COPY frontend/requirements.txt /app/frontend/requirements.txt
RUN pip install --no-cache-dir -r /app/frontend/requirements.txt

# App code (bump comment below to force no-cache for frontend on HF)
# Frontend copy: 2025-02-07
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY scripts/start_app_with_dashboard.sh /app/scripts/

ENV DISABLE_FILE_LOGGING=true
ENV AETHERIX_API_BASE=http://localhost:8000
# Visible in sidebar to confirm deployed build (update when pushing UI changes)
ENV AETHERIX_BUILD=2025-02-dashboard

EXPOSE 7860

RUN chmod +x /app/scripts/start_app_with_dashboard.sh
CMD ["/app/scripts/start_app_with_dashboard.sh"]
