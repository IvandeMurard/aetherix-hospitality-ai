"""
Obsidian vault integration — knowledge base, runbooks, and operational notes.

Writes / reads plain markdown files directly into the local Obsidian vault.
The vault syncs automatically via OneDrive, so no extra daemon is required.

Env vars required:
  OBSIDIAN_VAULT_PATH  — Absolute path to the vault root, e.g.
                         C:/Users/IVAN/OneDrive/Documents/Agentic AI Hospitality
                         or a Linux-mounted equivalent for containerised deployments.

Vault ID (reference only): 56343d2c29e9cb92
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Standard folder layout inside the vault
VAULT_FOLDERS = {
    "reports":   "AI Reports",
    "alerts":    "Alerts",
    "runbooks":  "Runbooks",
    "sync_logs": "Sync Logs",
}


def ensure_vault_structure() -> None:
    """Create the expected folder hierarchy inside the vault if missing."""
    vault = _vault()
    for folder in VAULT_FOLDERS.values():
        (vault / folder).mkdir(parents=True, exist_ok=True)


def _vault() -> Path:
    raw = os.environ["OBSIDIAN_VAULT_PATH"]
    p = Path(raw)
    if not p.is_dir():
        raise FileNotFoundError(f"Obsidian vault not found at {p}")
    return p


def _frontmatter(title: str, tags: list[str] | None = None) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tag_block = "\n".join(f"  - {t}" for t in (tags or []))
    tag_section = f"tags:\n{tag_block}\n" if tag_block else ""
    return f"---\ntitle: {title}\ncreated: {ts}\n{tag_section}---\n\n"


def write_note(
    title: str,
    content: str,
    folder: str = "AI Reports",
    tags: list[str] | None = None,
) -> Path:
    """
    Write (or overwrite) a markdown note inside *folder* relative to the vault root.

    Returns the absolute path of the written file.
    """
    target_dir = _vault() / folder
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(c if c.isalnum() or c in " -_()" else "_" for c in title).strip()
    note_path = target_dir / f"{safe_name}.md"
    note_path.write_text(_frontmatter(title, tags) + content, encoding="utf-8")
    return note_path


def read_note(relative_path: str) -> str:
    """Read and return the raw markdown content of a vault note."""
    return (_vault() / relative_path).read_text(encoding="utf-8")


def list_notes(folder: str = "AI Reports") -> list[dict[str, Any]]:
    """
    List all markdown notes in *folder* (non-recursive).

    Returns a list of dicts with ``name`` and ``modified`` keys.
    """
    target_dir = _vault() / folder
    if not target_dir.is_dir():
        return []
    return [
        {
            "name": p.stem,
            "path": str(p.relative_to(_vault())),
            "modified": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(),
        }
        for p in sorted(target_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    ]
