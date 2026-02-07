#!/bin/sh
# Run API (port 8000) and Streamlit dashboard (port 7860) for HuggingFace Space.
# HF exposes only port 7860, so the dashboard is the main entry; it calls the API at localhost:8000.
set -e
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
sleep 2
cd /app/frontend && exec streamlit run app.py --server.address 0.0.0.0 --server.port 7860
