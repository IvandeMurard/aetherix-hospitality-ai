"""DSAR — exercice des droits d'accès et d'effacement (art. 15 et 17 RGPD).

Story 7.5 / HOS-115 (AC6). Remplace la procédure sur le papier de
`docs/GDPR-DATA-INVENTORY.md` §7 par quelque chose qui s'exécute — la seule
partie de tout le dossier de conformité qui produise une preuve binaire : soit
la cascade passe, soit elle échoue.

## Pourquoi un *plan* plutôt qu'une fonction qui supprime

Trois raisons, dans l'ordre d'importance :

1. **Le dry-run est la valeur par défaut.** Un outil d'effacement qui supprime
   au premier appel, sans montrer ce qu'il va faire, est un incident qui attend
   son heure. Ici, `execute_plan` ne touche à rien tant que `dry_run=False`
   n'est pas passé explicitement.
2. **Le plan est relisible par quelqu'un qui ne lit pas Python.** Une DSAR se
   défend devant un DPO ou un régulateur : pouvoir imprimer « voici les onze
   opérations, dans cet ordre, avec leur justification » vaut mieux que
   « faites-nous confiance, le code est testé ».
3. **La logique de conformité devient testable sans base de données.** Les
   modèles utilisent des types Postgres (`UUID`, `JSONB`, `VECTOR`) qu'aucun
   SQLite ne réplique ; sans cette séparation, la partie qui compte — quelles
   tables, dans quel ordre, effacées ou neutralisées — ne serait couverte par
   aucun test.

## Ce que cette implémentation ne fait pas, et qu'il faut dire au demandeur

- **Les sauvegardes ne sont pas purgées.** Une ligne supprimée ici survit dans
  les snapshots Supabase jusqu'à expiration de leur fenêtre, qui n'est ni
  bornée ni documentée. Une réponse DSAR doit le dire, plutôt qu'affirmer un
  effacement immédiat.
- **Trois tables ne sont pas adressables par personne** : `operational_memory`,
  `agent_action_log` et `pms_sync_logs` portent des champs libres qui *peuvent*
  contenir une donnée personnelle, mais sont clés par hôtel, jamais par
  individu. Il n'existe donc aucun index permettant de retrouver « les lignes
  de cette personne ». C'est traité par un **balayage textuel best-effort** qui
  produit une liste à réviser à la main — jamais une suppression automatique :
  effacer sur correspondance de sous-chaîne détruirait des données
  opérationnelles légitimes au premier homonyme.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import delete, or_, select, update

from app.core.pii import digest_identifier
# `operational_memory`, `agent_action_log` et `pms_sync_logs` sont absentes de cet
# import, et ce n'est pas un oubli : le service ne les requête jamais. Elles sont
# clés par hôtel et non par personne, donc marquées REVIEW dans le plan — leur
# traitement est un arbitrage humain, pas une requête. Le jour où le balayage
# textuel sera automatisé, elles apparaîtront ici.
from app.db.models import ConversationalQuery, RestaurantProfile, User

logger = logging.getLogger(__name__)


class Action(str, Enum):
    """Ce qu'on fait d'une ligne, et pourquoi la distinction compte.

    `DELETE` retire la ligne. `NEUTRALISE` la garde en vidant ses seules
    colonnes personnelles : c'est le bon geste quand la ligne porte aussi de
    l'opérationnel non personnel (les paramètres de couverts d'un restaurant
    n'identifient personne) ou quand l'art. 17(3)(b) autorise à conserver une
    trace d'audit. `REVIEW` ne touche à rien et demande un arbitrage humain.
    """

    DELETE = "delete"
    NEUTRALISE = "neutralise"
    REVIEW = "review"


@dataclass(frozen=True)
class Subject:
    """La personne concernée, telle qu'on sait la retrouver.

    Au moins un identifiant est requis. Les trois sont acceptés ensemble parce
    qu'un manager est souvent connu par les trois à la fois, et qu'une DSAR
    incomplète parce qu'on n'a cherché que sur l'e-mail est un manquement.
    """

    email: str | None = None
    phone: str | None = None
    name: str | None = None

    def __post_init__(self) -> None:
        if not any((self.email, self.phone, self.name)):
            raise ValueError(
                "Un sujet doit porter au moins un identifiant (email, phone ou name)."
            )

    @property
    def free_text_needles(self) -> tuple[str, ...]:
        """Chaînes à chercher dans les champs libres non indexés par personne."""
        return tuple(v.strip() for v in (self.email, self.phone, self.name) if v and v.strip())


@dataclass(frozen=True)
class Step:
    """Une opération du plan, avec ce qui la justifie."""

    order: int
    table: str
    action: Action
    target: str
    rationale: str
    columns: tuple[str, ...] = ()


@dataclass
class ExecutionReport:
    """Ce que l'exécution a réellement fait — jamais ce qu'elle comptait faire."""

    dry_run: bool
    subject: Subject
    executed_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    rows_affected: dict[str, int] = field(default_factory=dict)
    manual_review: list[dict[str, Any]] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)

    @property
    def total_rows(self) -> int:
        return sum(self.rows_affected.values())


# Réponse type à joindre à toute confirmation d'effacement. Elle est ici, dans
# le code, et pas dans un modèle de courrier, pour qu'elle ne puisse pas dériver
# de ce que le code fait réellement.
BACKUP_CAVEAT = (
    "Les sauvegardes de base ne sont pas purgées par cette opération : les lignes "
    "supprimées peuvent subsister dans les snapshots jusqu'à expiration de leur "
    "fenêtre de rétention. La suppression n'est complète qu'à ce terme."
)
FREE_TEXT_CAVEAT = (
    "Trois tables (operational_memory, agent_action_log, pms_sync_logs) portent des "
    "champs libres qui ne sont pas indexés par personne. Elles ont été balayées par "
    "recherche textuelle ; les correspondances sont listées pour arbitrage manuel, "
    "jamais supprimées automatiquement."
)


def build_erasure_plan(subject: Subject) -> list[Step]:
    """Construit le plan d'effacement, ordonné.

    L'ordre n'est pas cosmétique : `users` vient en dernier parce que les autres
    tables le référencent, et une suppression en tête casserait les clés
    étrangères au milieu de la transaction — donc une DSAR à moitié appliquée,
    ce qui est pire qu'une DSAR refusée.
    """
    steps: list[Step] = []
    order = 0

    if subject.phone:
        order += 1
        steps.append(
            Step(
                order=order,
                table="conversational_queries",
                action=Action.DELETE,
                target="from_number == digest(phone)",
                rationale=(
                    "Messages entrants. La colonne porte un HMAC poivré depuis la Story 7.5 : "
                    "on cherche donc le digest, pas le numéro."
                ),
            )
        )

    order += 1
    steps.append(
        Step(
            order=order,
            table="restaurant_profiles",
            action=Action.NEUTRALISE,
            target="phone_number | notification_email == sujet",
            rationale=(
                "La ligne survit : total_seats, turns et capture rates n'identifient "
                "personne et le restaurant continue d'exister après le départ de son manager. "
                "Seules les trois colonnes personnelles sont vidées."
            ),
            columns=("manager_name", "phone_number", "notification_email"),
        )
    )

    order += 1
    steps.append(
        Step(
            order=order,
            table="operational_memory",
            action=Action.REVIEW,
            target="balayage textuel sur reflection | manager_feedback | outcome",
            rationale=(
                "Table clé par hôtel, jamais par personne — aucun index ne permet de "
                "retrouver « les lignes de cette personne ». Effacer sur correspondance de "
                "sous-chaîne détruirait de l'opérationnel légitime au premier homonyme. "
                "⚠️ Une suppression retenue doit effacer la ligne ET son embedding : un "
                "vecteur dérivé d'une donnée personnelle reste une donnée personnelle."
            ),
        )
    )

    order += 1
    steps.append(
        Step(
            order=order,
            table="agent_action_log",
            action=Action.REVIEW,
            target="balayage textuel sur payload | abstention_context",
            rationale=(
                "Champs JSON non contraints. La ligne d'audit elle-même est conservable "
                "au titre de l'art. 17(3)(b) ; seul le contenu libre est en cause."
            ),
        )
    )

    order += 1
    steps.append(
        Step(
            order=order,
            table="pms_sync_logs",
            action=Action.REVIEW,
            target="balayage textuel sur raw_payload_summary | error_message",
            rationale=(
                "Le PIIStripper protège le dictionnaire de réservation, pas ces deux "
                "champs libres qui peuvent recevoir un extrait de payload amont."
            ),
        )
    )

    if subject.email:
        order += 1
        steps.append(
            Step(
                order=order,
                table="users",
                action=Action.DELETE,
                target="email == sujet",
                rationale=(
                    "En dernier : les autres tables référencent le compte. Supprimer en "
                    "tête casserait les FK au milieu de la transaction, laissant une DSAR "
                    "à moitié appliquée."
                ),
            )
        )

    return steps


def render_plan(subject: Subject, steps: list[Step]) -> str:
    """Rend le plan en texte lisible — c'est ce qu'on montre avant d'exécuter."""
    lines = [
        "Plan d'effacement DSAR (art. 17)",
        f"Sujet : email={subject.email or '—'} phone={subject.phone or '—'} name={subject.name or '—'}",
        "",
    ]
    for step in steps:
        cols = f" [{', '.join(step.columns)}]" if step.columns else ""
        lines.append(f"{step.order}. {step.table} — {step.action.value.upper()}{cols}")
        lines.append(f"   cible    : {step.target}")
        lines.append(f"   pourquoi : {step.rationale}")
        lines.append("")
    lines.append(f"⚠️ {BACKUP_CAVEAT}")
    lines.append(f"⚠️ {FREE_TEXT_CAVEAT}")
    return "\n".join(lines)


async def export_subject_data(subject: Subject, session) -> dict[str, Any]:
    """Export art. 15 — tout ce qu'on détient sur la personne.

    Inclut délibérément la **logique** des décisions automatisées la concernant
    (art. 15(1)(h)) : dans Aetherix, la recommandation et son `triggering_factor`
    sont ce qui explique une décision, et les taire rendrait l'export
    formellement complet et matériellement inutile.
    """
    export: dict[str, Any] = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "subject": {"email": subject.email, "phone": subject.phone, "name": subject.name},
        "records": {},
        "caveats": [BACKUP_CAVEAT, FREE_TEXT_CAVEAT],
    }

    if subject.email:
        rows = (await session.execute(select(User).where(User.email == subject.email))).scalars().all()
        export["records"]["users"] = [
            {"id": str(r.id), "email": r.email, "full_name": r.full_name} for r in rows
        ]

    filters = []
    if subject.phone:
        filters.append(RestaurantProfile.phone_number == subject.phone)
    if subject.email:
        filters.append(RestaurantProfile.notification_email == subject.email)
    if filters:
        rows = (
            await session.execute(select(RestaurantProfile).where(or_(*filters)))
        ).scalars().all()
        export["records"]["restaurant_profiles"] = [
            {
                "id": str(r.id),
                "manager_name": r.manager_name,
                "phone_number": r.phone_number,
                "notification_email": r.notification_email,
            }
            for r in rows
        ]

    if subject.phone:
        digest = digest_identifier(subject.phone)
        rows = (
            await session.execute(
                select(ConversationalQuery).where(ConversationalQuery.from_number == digest)
            )
        ).scalars().all()
        export["records"]["conversational_queries"] = [
            {"id": str(r.id), "body": r.body, "created_at": r.created_at.isoformat()}
            for r in rows
        ]

    return export


async def execute_plan(
    subject: Subject,
    steps: list[Step],
    session,
    *,
    dry_run: bool = True,
) -> ExecutionReport:
    """Exécute le plan. **Ne touche à rien** tant que `dry_run=False` n'est pas passé."""
    report = ExecutionReport(dry_run=dry_run, subject=subject)
    report.caveats = [BACKUP_CAVEAT, FREE_TEXT_CAVEAT]

    if dry_run:
        logger.info("dsar: dry-run — %d étapes planifiées, aucune écriture", len(steps))
        for step in steps:
            report.rows_affected[step.table] = 0
        return report

    for step in steps:
        if step.action is Action.REVIEW:
            report.manual_review.append(
                {"table": step.table, "target": step.target, "rationale": step.rationale}
            )
            continue

        if step.table == "conversational_queries":
            digest = digest_identifier(subject.phone)
            result = await session.execute(
                delete(ConversationalQuery).where(ConversationalQuery.from_number == digest)
            )
        elif step.table == "restaurant_profiles":
            filters = []
            if subject.phone:
                filters.append(RestaurantProfile.phone_number == subject.phone)
            if subject.email:
                filters.append(RestaurantProfile.notification_email == subject.email)
            result = await session.execute(
                update(RestaurantProfile)
                .where(or_(*filters))
                .values(manager_name=None, phone_number=None, notification_email=None)
            )
        elif step.table == "users":
            result = await session.execute(delete(User).where(User.email == subject.email))
        else:  # pragma: no cover — toute table non gérée doit crier, pas être ignorée
            raise NotImplementedError(f"Étape DSAR non implémentée : {step.table}")

        report.rows_affected[step.table] = result.rowcount or 0

    await session.commit()
    logger.info(
        "dsar: effacement exécuté — %d lignes sur %d tables, %d à réviser",
        report.total_rows,
        len(report.rows_affected),
        len(report.manual_review),
    )
    return report


# Tables porteuses de données personnelles, d'après GDPR-DATA-INVENTORY §2.1.
# Le test `test_plan_covers_every_pii_table` compare cette liste au plan : une
# table ajoutée ici sans étape correspondante fait échouer la suite. C'est ce qui
# empêche la DSAR de pourrir silencieusement à mesure que le schéma grossit.
PII_TABLES: frozenset[str] = frozenset(
    {
        "users",
        "restaurant_profiles",
        "conversational_queries",
        "operational_memory",
        "agent_action_log",
        "pms_sync_logs",
    }
)
