"""Purge de rétention — Story 7.5 / HOS-115 (AC5).

Premier job de rétention du système. Jusqu'ici, **rien ne supprimait rien** :
les durées de conservation existaient dans la documentation et nulle part
ailleurs, ce qui est la définition d'une durée non respectée (art. 5(1)(e)).

Portée volontairement réduite à `conversational_queries` : c'est la table la
plus exposée (`docs/GDPR-DATA-INVENTORY.md` §6.2) — texte libre saisi par un
manager, expéditeur pas nécessairement client, aucune base légale pour un
numéro inconnu qui écrit par erreur. Les sept autres durées du §4 de
l'inventaire suivront ; les câbler toutes d'un coup sans les tester une par une
serait le meilleur moyen de supprimer ce qu'il ne fallait pas.

Deux propriétés que ce job doit avoir, et qu'il est facile de rater :

  - **Idempotent.** Rejouable sans dommage : la seconde exécution ne trouve
    plus rien.
  - **Bavard sur ce qu'il a fait.** Une suppression silencieuse est
    indistinguable d'un job qui n'a jamais tourné — et c'est précisément la
    confusion qui a produit la situation actuelle. Le compte va dans les logs
    et dans `scheduler_event` via le heartbeat.

Ce que ce job ne fait **pas** : purger les sauvegardes. Une ligne supprimée ici
survit dans les snapshots Supabase jusqu'à expiration de leur propre fenêtre,
qui n'est ni bornée ni documentée (inventaire §8, point 7). La suppression n'est
donc complète qu'au bout de cette fenêtre — à dire tel quel dans une réponse
DSAR, plutôt que d'affirmer un effacement immédiat.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import delete

from app.core import config
from app.db.models import ConversationalQuery
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

JOB_ID = "retention_purge"


async def purge_conversational_queries(now: datetime | None = None) -> int:
    """Supprime les messages entrants au-delà de la durée de conservation.

    Args:
        now: instant de référence (injecté par les tests).

    Returns:
        Nombre de lignes supprimées.
    """
    reference = now or datetime.now(tz=timezone.utc)
    cutoff = reference - timedelta(days=config.CONVERSATIONAL_QUERY_RETENTION_DAYS)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(ConversationalQuery).where(ConversationalQuery.created_at < cutoff)
        )
        await session.commit()

    deleted = result.rowcount or 0
    logger.info(
        "retention_purge: conversational_queries deleted=%d cutoff=%s retention_days=%d",
        deleted,
        cutoff.isoformat(),
        config.CONVERSATIONAL_QUERY_RETENTION_DAYS,
    )
    return deleted


async def run_retention_purge() -> None:
    """Point d'entrée APScheduler.

    Une exception ici ne doit pas tuer le scheduler partagé — mais elle ne doit
    pas non plus disparaître : un job de rétention muet qui échoue depuis trois
    mois est exactement le scénario que cette story corrige.
    """
    try:
        await purge_conversational_queries()
    except Exception:
        logger.exception("retention_purge: failed")
        try:
            from app.services.ops_dispatcher import dispatch_error

            await dispatch_error(
                title="Purge de rétention échouée",
                detail=(
                    "`retention_purge` n'a pas pu supprimer les `conversational_queries` "
                    "expirées. Les données personnelles sont conservées au-delà de leur "
                    "durée déclarée tant que ce job ne repasse pas (art. 5(1)(e))."
                ),
            )
        except Exception:
            logger.exception("retention_purge: dispatch_error failed too")


def register_retention_purge_job(scheduler: AsyncIOScheduler) -> None:
    """Enregistre la purge quotidienne sur le scheduler partagé."""
    scheduler.add_job(
        run_retention_purge,
        trigger=CronTrigger(hour=config.RETENTION_PURGE_HOUR, minute=0, timezone="UTC"),
        id=JOB_ID,
        replace_existing=True,
    )
    logger.info(
        "retention_purge: job registered (daily %02d:00 UTC, retention=%d days)",
        config.RETENTION_PURGE_HOUR,
        config.CONVERSATIONAL_QUERY_RETENTION_DAYS,
    )
