"""Obsidian vault integration — read/write markdown notes."""
import os
import re
from datetime import datetime
from pathlib import Path

# Logical vault sub-folders for ops dispatch targets. Single source of truth —
# consumed by ops_dispatcher (alerts/reports), pms_sync (sync_logs) and
# reporting_service (reports). Paths are relative to OBSIDIAN_VAULT_PATH;
# write_note() creates them on demand.
#
# HOS-211: this constant was imported by those callers but never defined here,
# so reporting_service._dispatch_ops raised ImportError → GET /reports/weekly
# returned 500 (the ops_dispatcher imports sat inside try/except and failed
# silently instead). Defined here once to fix all consumers.
VAULT_FOLDERS: dict[str, str] = {
    "reports": "AI Reports/Operational",  # weekly audits, ROI digests
    "alerts": "AI Reports/Alerts",        # error + anomaly mirrors of Linear issues
    "sync_logs": "AI Reports/Sync Logs",  # PMS sync run logs
}


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
