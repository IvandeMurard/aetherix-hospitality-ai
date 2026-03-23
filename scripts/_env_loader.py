"""
scripts/_env_loader.py
Charge automatiquement le fichier .env à la racine du repo.
Aucune dépendance externe — fonctionne en local, CI et Claude Code cloud.

Usage dans n'importe quel script :
    from _env_loader import load_env
    load_env()
"""
from __future__ import annotations

import os
from pathlib import Path


def load_env(env_file: Path | None = None) -> int:
    """
    Charge les variables du fichier .env dans os.environ.
    N'écrase PAS les variables déjà définies (GitHub Secrets, shell, etc.).
    Retourne le nombre de variables chargées.
    """
    if env_file is None:
        env_file = Path(__file__).parent.parent / ".env"

    if not env_file.exists():
        return 0

    loaded = 0
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded += 1

    return loaded
