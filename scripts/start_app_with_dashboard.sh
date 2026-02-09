#!/bin/sh
# Run API (port 8000), Streamlit dashboard (port 8501), and nginx reverse proxy (port 7860) for HuggingFace Space.
# HF exposes only port 7860. nginx routes API requests to FastAPI:8000 and everything else to Streamlit:8501.
set -e

echo "[STARTUP] Starting services..."

# Verify nginx config
echo "[STARTUP] Verifying nginx configuration..."
nginx -t || {
    echo "[STARTUP] ERROR: nginx configuration test failed!"
    cat /etc/nginx/nginx.conf
    exit 1
}
echo "[STARTUP] nginx configuration OK"

# Start FastAPI backend on port 8000 (background)
echo "[STARTUP] Starting FastAPI on port 8000..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
FASTAPI_PID=$!
sleep 3

# Verify FastAPI is running
if ! kill -0 $FASTAPI_PID 2>/dev/null; then
    echo "[STARTUP] ERROR: FastAPI failed to start!"
    exit 1
fi
echo "[STARTUP] FastAPI started (PID: $FASTAPI_PID)"

# Test FastAPI health endpoint
echo "[STARTUP] Testing FastAPI health endpoint..."
for i in 1 2 3 4 5; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "[STARTUP] FastAPI health check OK"
        break
    fi
    if [ $i -eq 5 ]; then
        echo "[STARTUP] WARNING: FastAPI health check failed after 5 attempts"
    else
        echo "[STARTUP] Waiting for FastAPI... (attempt $i/5)"
        sleep 2
    fi
done

# Start Streamlit dashboard on port 8501 (background)
echo "[STARTUP] Starting Streamlit on port 8501..."
cd /app/frontend && streamlit run app.py --server.address 0.0.0.0 --server.port 8501 &
STREAMLIT_PID=$!
sleep 5

# Verify Streamlit is running
if ! kill -0 $STREAMLIT_PID 2>/dev/null; then
    echo "[STARTUP] ERROR: Streamlit failed to start!"
    exit 1
fi
echo "[STARTUP] Streamlit started (PID: $STREAMLIT_PID)"

# Test Streamlit is responding
echo "[STARTUP] Testing Streamlit endpoint..."
for i in 1 2 3 4 5; do
    if curl -s http://localhost:8501 > /dev/null 2>&1; then
        echo "[STARTUP] Streamlit health check OK"
        break
    fi
    if [ $i -eq 5 ]; then
        echo "[STARTUP] WARNING: Streamlit health check failed after 5 attempts"
    else
        echo "[STARTUP] Waiting for Streamlit... (attempt $i/5)"
        sleep 2
    fi
done

# Start nginx reverse proxy on port 7860 (foreground - this keeps the container alive)
echo "[STARTUP] Starting nginx on port 7860..."
echo "[STARTUP] Services ready. nginx will route:"
echo "[STARTUP]   - /predict, /api/*, /health -> FastAPI:8000"
echo "[STARTUP]   - /, /_stcore/stream -> Streamlit:8501"
exec nginx -g 'daemon off;'
