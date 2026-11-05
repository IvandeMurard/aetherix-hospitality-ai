"""The WhatsApp demo script (scripts/ops/demo_whatsapp_conversation.py) keeps
running on the production services, scripted mode, no network. A demo that
breaks the day before it is shown is worse than none."""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "ops" / "demo_whatsapp_conversation.py"


def _load():
    spec = importlib.util.spec_from_file_location("demo_whatsapp_conversation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_conversation_runs_and_records_each_path(capsys):
    asyncio.run(_load().run(None))
    out = capsys.readouterr().out
    assert "SCRIPTÉ (aucun modèle appelé)" in out           # never passed off as a model
    assert "Validation enregistrée." in out                  # bare ack
    assert "Refus enregistré. Une raison ? (facultatif)" in out
    assert "Correction enregistrée : 3 extras." in out       # counter figure echoed
    assert "Je note un refus, c'est bien ça ?" in out         # < 0.85 → confirmation
    assert "je remplace une validation par un refus" in out  # revision asks first
    assert "Récap semaine" in out
    assert "source manager_revision" in out and "source model_confirmed" in out
