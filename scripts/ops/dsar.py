#!/usr/bin/env python3
"""Outil opérateur DSAR — Story 7.5 / HOS-115 (AC6).

Exercice des droits d'accès (art. 15) et d'effacement (art. 17) sur demande
d'une personne concernée. C'est l'outil qu'on ouvre quand une demande arrive,
pas une bibliothèque : il tient le délai d'un mois de l'art. 12(3) précisément
parce qu'il n'y a rien à réinventer sur le moment.

  # Voir ce qui serait supprimé — comportement par défaut, aucune écriture
  python scripts/ops/dsar.py --phone "+33612345678" --erase

  # Exporter (art. 15)
  python scripts/ops/dsar.py --email manager@hotel.example --export

  # Supprimer pour de vrai — exige --confirm en plus de --erase
  python scripts/ops/dsar.py --phone "+33612345678" --erase --confirm

Le double verrou (`--erase` puis `--confirm`) est délibéré : une suppression de
données personnelles est irréversible et se déclenche sur une demande écrite.
Un seul drapeau, et une faute de frappe dans un terminal suffit.

Codes de sortie : 0 succès · 1 sujet introuvable · 2 erreur d'usage.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

# Le plan porte des emojis d'avertissement ; un terminal Windows par défaut est en
# cp1252 et lèverait UnicodeEncodeError au moment précis où l'opérateur a besoin de
# lire les réserves. Même correctif que scripts/ops/hygiene_architecturale.py.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services.dsar import (  # noqa: E402
    Subject,
    build_erasure_plan,
    execute_plan,
    export_subject_data,
    render_plan,
)


async def _run(args: argparse.Namespace) -> int:
    subject = Subject(email=args.email, phone=args.phone, name=args.name)

    async with AsyncSessionLocal() as session:
        if args.export:
            payload = await export_subject_data(subject, session)
            found = sum(len(v) for v in payload["records"].values())
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            if found == 0:
                print("\n⚠️  Aucun enregistrement trouvé pour ce sujet.", file=sys.stderr)
                return 1
            return 0

        steps = build_erasure_plan(subject)
        print(render_plan(subject, steps))

        if not args.confirm:
            print(
                "\n🔒 DRY-RUN — aucune écriture effectuée. "
                "Ajouter --confirm pour exécuter ce plan.",
                file=sys.stderr,
            )
            await execute_plan(subject, steps, session, dry_run=True)
            return 0

        report = await execute_plan(subject, steps, session, dry_run=False)
        print("\n--- Exécuté ---")
        for table, count in report.rows_affected.items():
            print(f"  {table:28s} {count} ligne(s)")
        if report.manual_review:
            print("\n--- À réviser à la main (non supprimé) ---")
            for item in report.manual_review:
                print(f"  {item['table']:28s} {item['target']}")
        print(f"\nTotal : {report.total_rows} ligne(s) traitée(s) à {report.executed_at.isoformat()}")
        for caveat in report.caveats:
            print(f"\n⚠️  {caveat}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Outil DSAR (RGPD art. 15 / 17)")
    parser.add_argument("--email", help="E-mail de la personne concernée")
    parser.add_argument("--phone", help="Téléphone de la personne concernée (E.164)")
    parser.add_argument("--name", help="Nom — utilisé pour le balayage des champs libres")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--export", action="store_true", help="Export art. 15")
    mode.add_argument("--erase", action="store_true", help="Effacement art. 17 (dry-run par défaut)")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Exécute réellement l'effacement. Sans ce drapeau, --erase est un dry-run.",
    )
    args = parser.parse_args()

    if not any((args.email, args.phone, args.name)):
        parser.error("Au moins un identifiant est requis : --email, --phone ou --name.")
    if args.confirm and not args.erase:
        parser.error("--confirm n'a de sens qu'avec --erase.")

    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
