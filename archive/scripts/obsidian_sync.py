"""
Synchronisation automatique : Repo Git → Vault Obsidian

Fonctionnement :
  1. git pull (récupère les derniers artefacts BMAD, notes de session, etc.)
  2. Copie docs/bmad/_bmad-output/ → Vault Obsidian/AI Reports/BMAD/
  3. Met à jour une note index dans le vault

Usage :
  python scripts/obsidian_sync.py              # pull + sync
  python scripts/obsidian_sync.py --no-pull    # sync seulement
  python scripts/obsidian_sync.py --dry-run    # aperçu sans écrire
"""

import os
import sys
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# ─── Configuration ────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.resolve()

VAULT_ROOT = Path(r"C:\Users\IVAN\OneDrive\Documents\Agentic AI Hospitality")

# Dossier de destination dans le vault (créé automatiquement s'il n'existe pas)
VAULT_BMAD_DIR = VAULT_ROOT / "AI Reports" / "BMAD"

# Sources à synchroniser : (source_relative_to_repo, destination_relative_to_vault_bmad)
SYNC_SOURCES = [
    (REPO_ROOT / "docs" / "bmad" / "_bmad-output" / "planning-artifacts",     "Planning"),
    (REPO_ROOT / "docs" / "bmad" / "_bmad-output" / "implementation-artifacts","Implementation"),
]

# Note index dans le vault
INDEX_NOTE = VAULT_ROOT / "AI Reports" / "BMAD" / "_Index.md"

# ─── Helpers ──────────────────────────────────────────────────────────────────

def log(msg: str, level: str = "INFO"):
    prefix = {"INFO": "[·]", "OK": "[✓]", "WARN": "[!]", "ERR": "[✗]"}.get(level, "[·]")
    print(f"{prefix} {msg}")


def git_pull(dry_run: bool) -> bool:
    """Lance git pull sur le repo. Retourne True si succès."""
    log(f"git pull — {REPO_ROOT.name}")
    if dry_run:
        log("(dry-run) git pull ignoré", "WARN")
        return True
    try:
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            summary = result.stdout.strip().split("\n")[-1]
            log(summary, "OK")
            return True
        else:
            log(f"git pull a échoué : {result.stderr.strip()}", "ERR")
            return False
    except subprocess.TimeoutExpired:
        log("git pull timeout (>30s) — vérifier la connexion", "ERR")
        return False
    except FileNotFoundError:
        log("git introuvable dans le PATH", "ERR")
        return False


def sync_folder(src: Path, dest: Path, dry_run: bool) -> tuple[int, int]:
    """Copie les fichiers .md de src vers dest. Retourne (copiés, ignorés)."""
    if not src.exists():
        log(f"Source introuvable, ignorée : {src}", "WARN")
        return 0, 0

    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)

    copied, skipped = 0, 0
    for md_file in sorted(src.glob("*.md")):
        dest_file = dest / md_file.name
        # Copier seulement si la source est plus récente
        if dest_file.exists():
            src_mtime = md_file.stat().st_mtime
            dst_mtime = dest_file.stat().st_mtime
            if src_mtime <= dst_mtime:
                skipped += 1
                continue
        if dry_run:
            log(f"(dry-run) copierait : {md_file.name} → {dest.name}/")
        else:
            shutil.copy2(md_file, dest_file)
            log(f"{md_file.name} → {dest.name}/", "OK")
        copied += 1

    return copied, skipped


def write_index(dry_run: bool):
    """Écrit/met à jour la note _Index.md dans le vault."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# BMAD — Index des artefacts\n",
        f"*Dernière synchronisation : {now}*\n\n",
        "## Planning\n",
    ]
    planning_dir = VAULT_BMAD_DIR / "Planning"
    if planning_dir.exists():
        for f in sorted(planning_dir.glob("*.md")):
            lines.append(f"- [[Planning/{f.stem}]]\n")
    lines += ["\n## Implementation\n"]
    impl_dir = VAULT_BMAD_DIR / "Implementation"
    if impl_dir.exists():
        for f in sorted(impl_dir.glob("*.md")):
            lines.append(f"- [[Implementation/{f.stem}]]\n")

    content = "".join(lines)
    if dry_run:
        log("(dry-run) _Index.md non écrit")
        return
    INDEX_NOTE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_NOTE.write_text(content, encoding="utf-8")
    log("_Index.md mis à jour", "OK")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sync repo → Obsidian vault")
    parser.add_argument("--no-pull",  action="store_true", help="Saute le git pull")
    parser.add_argument("--dry-run",  action="store_true", help="Simulation sans écriture")
    args = parser.parse_args()

    print(f"\n{'─'*55}")
    print(f"  Obsidian Sync  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'─'*55}\n")

    # 1. Git pull
    if not args.no_pull:
        ok = git_pull(args.dry_run)
        if not ok:
            log("Sync annulée (pull échoué). Utiliser --no-pull pour forcer.", "ERR")
            sys.exit(1)
        print()

    # 2. Vérifier que le vault existe
    if not args.dry_run and not VAULT_ROOT.exists():
        log(f"Vault Obsidian introuvable : {VAULT_ROOT}", "ERR")
        log("Vérifier que OneDrive est monté et que le chemin est correct.", "WARN")
        sys.exit(1)

    # 3. Synchroniser chaque source
    total_copied = total_skipped = 0
    for src, dest_name in SYNC_SOURCES:
        dest = VAULT_BMAD_DIR / dest_name
        copied, skipped = sync_folder(src, dest, args.dry_run)
        total_copied += copied
        total_skipped += skipped

    # 4. Mettre à jour l'index
    print()
    write_index(args.dry_run)

    # 5. Résumé
    print(f"\n{'─'*55}")
    log(f"Terminé — {total_copied} fichier(s) synchronisé(s), {total_skipped} inchangé(s)", "OK")
    print(f"{'─'*55}\n")


if __name__ == "__main__":
    main()
