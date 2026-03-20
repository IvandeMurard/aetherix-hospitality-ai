"""
Local uvicorn launcher that explicitly loads the workspace root `.env`.

Why: when running uvicorn directly from the host, the app does not
auto-load `.env`, so Twilio credentials (TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN)
may be missing. This causes inbound webhooks to be received but the outbound
WhatsApp reply to fail (401).
"""

from __future__ import annotations

import importlib

import uvicorn
from dotenv import load_dotenv


def main() -> None:
    # `fastapi-backend/` -> repo root `.env`
    load_dotenv(dotenv_path="../.env")

    app = importlib.import_module("app.main").app
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()

