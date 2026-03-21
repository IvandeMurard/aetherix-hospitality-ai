"""Obsidian vault integration — read/write markdown notes."""
import os
import re
from datetime import datetime
from pathlib import Path


def _vault() -> Path:
    path = os.environ.get("OBSIDIAN_VAULT_PATH", "/vault")
    return Path(path)


def write_note(
    title: str,
    content: str,
    folder: str = "",
    tags: list[str] | None = None,
) -> str:
    """Write (or overwrite) a markdown note in the vault.

    Returns the absolute path of the written file.
    """
    vault = _vault()
    target_dir = vault / folder if folder else vault
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_title = re.sub(r'[\\/*?:"<>|]', "-", title)
    filepath = target_dir / f"{safe_title}.md"

    frontmatter_tags = ""
    if tags:
        tag_list = "\n".join(f"  - {t}" for t in tags)
        frontmatter_tags = f"tags:\n{tag_list}\n"

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    note = f"---\ntitle: {title}\ndate: {now}\n{frontmatter_tags}---\n\n{content}\n"

    filepath.write_text(note, encoding="utf-8")
    return str(filepath)


def list_notes(folder: str = "") -> list[str]:
    """Return a list of note filenames (*.md) in the given folder."""
    target = _vault() / folder if folder else _vault()
    if not target.exists():
        return []
    return [f.name for f in sorted(target.glob("*.md"))]


def read_note(title: str, folder: str = "") -> str | None:
    """Read note content (without frontmatter) by title. Returns None if not found."""
    vault = _vault()
    target_dir = vault / folder if folder else vault
    safe_title = re.sub(r'[\\/*?:"<>|]', "-", title)
    filepath = target_dir / f"{safe_title}.md"
    if not filepath.exists():
        return None
    raw = filepath.read_text(encoding="utf-8")
    # Strip YAML frontmatter
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        return parts[2].strip() if len(parts) >= 3 else raw
    return raw
