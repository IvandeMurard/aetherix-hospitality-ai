"""DSAR — Story 7.5 / HOS-115 (AC6).

Ce que ces tests garantissent, par ordre d'importance pour la conformité :

  1. **Le plan couvre toutes les tables porteuses de PII.** C'est le test qui
     empêche la DSAR de pourrir : ajouter une table à l'inventaire sans étape
     correspondante fait échouer la suite.
  2. **Le dry-run n'écrit rien.** Une DSAR qui supprime en mode aperçu est un
     incident, pas un bug.
  3. **L'ordre est respecté** — `users` en dernier, sinon les FK cassent au
     milieu de la transaction et la demande reste à moitié appliquée.
  4. **Les réserves sont toujours présentes.** Le paragraphe sur les sauvegardes
     n'est pas décoratif : sans lui, on affirme au demandeur un effacement
     immédiat qui n'a pas eu lieu.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import config
from app.services.dsar import (
    BACKUP_CAVEAT,
    FREE_TEXT_CAVEAT,
    PII_TABLES,
    Action,
    Subject,
    build_erasure_plan,
    execute_plan,
    render_plan,
)


@pytest.fixture(autouse=True)
def _pepper(monkeypatch):
    monkeypatch.setattr(config, "PII_HASH_PEPPER", "test-pepper-not-a-real-secret")


def _full_subject() -> Subject:
    return Subject(
        email="manager@hotel.example",
        phone="+33612345678",
        name="Amélie Rousseau-Kowalski",
    )


class TestSubject:
    def test_requires_at_least_one_identifier(self):
        with pytest.raises(ValueError):
            Subject()

    @pytest.mark.parametrize(
        "kwargs", [{"email": "a@b.c"}, {"phone": "+33612345678"}, {"name": "X"}]
    )
    def test_one_identifier_is_enough(self, kwargs):
        assert Subject(**kwargs) is not None

    def test_free_text_needles_drop_empty_values(self):
        subject = Subject(email="a@b.c", phone="   ", name=None)
        assert subject.free_text_needles == ("a@b.c",)


class TestErasurePlan:
    def test_plan_covers_every_pii_table(self):
        """Le garde-fou. Une table PII sans étape = suite rouge.

        `PII_TABLES` reflète GDPR-DATA-INVENTORY §2.1. Le jour où une colonne
        personnelle apparaît dans une nouvelle table, elle est ajoutée là — et
        ce test réclame l'étape correspondante avant de repasser au vert.
        """
        planned = {step.table for step in build_erasure_plan(_full_subject())}
        missing = PII_TABLES - planned
        assert not missing, f"Tables PII sans étape DSAR : {sorted(missing)}"

    def test_users_comes_last(self):
        """Les autres tables référencent le compte : le supprimer en tête casse les FK."""
        steps = build_erasure_plan(_full_subject())
        assert steps[-1].table == "users"

    def test_orders_are_contiguous_and_sorted(self):
        steps = build_erasure_plan(_full_subject())
        assert [s.order for s in steps] == list(range(1, len(steps) + 1))

    def test_restaurant_profile_is_neutralised_not_deleted(self):
        """Le restaurant survit au départ de son manager — la ligne porte de l'opérationnel."""
        step = next(
            s for s in build_erasure_plan(_full_subject()) if s.table == "restaurant_profiles"
        )
        assert step.action is Action.NEUTRALISE
        assert set(step.columns) == {"manager_name", "phone_number", "notification_email"}

    def test_unindexed_tables_are_review_never_delete(self):
        """Effacer sur correspondance de sous-chaîne détruirait l'opérationnel au 1er homonyme."""
        unindexed = {"operational_memory", "agent_action_log", "pms_sync_logs"}
        for step in build_erasure_plan(_full_subject()):
            if step.table in unindexed:
                assert step.action is Action.REVIEW

    def test_no_phone_means_no_conversational_queries_step(self):
        """Sans numéro, la table des messages entrants n'est pas adressable."""
        steps = build_erasure_plan(Subject(email="a@b.c"))
        assert not any(s.table == "conversational_queries" for s in steps)

    def test_no_email_means_no_users_step(self):
        steps = build_erasure_plan(Subject(phone="+33612345678"))
        assert not any(s.table == "users" for s in steps)

    def test_every_step_carries_a_rationale(self):
        """Un plan se défend devant un DPO : chaque opération dit pourquoi elle existe."""
        for step in build_erasure_plan(_full_subject()):
            assert len(step.rationale) > 40, f"Étape sans justification : {step.table}"


class TestRenderPlan:
    def test_mentions_both_caveats(self):
        """Sans elles, on affirme au demandeur un effacement qui n'a pas complètement eu lieu."""
        rendered = render_plan(_full_subject(), build_erasure_plan(_full_subject()))
        assert BACKUP_CAVEAT in rendered
        assert FREE_TEXT_CAVEAT in rendered

    def test_lists_every_step(self):
        steps = build_erasure_plan(_full_subject())
        rendered = render_plan(_full_subject(), steps)
        for step in steps:
            assert step.table in rendered


class TestExecution:
    @pytest.mark.asyncio
    async def test_dry_run_touches_nothing(self):
        """Le test le plus important du fichier."""
        session = MagicMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        subject = _full_subject()
        report = await execute_plan(
            subject, build_erasure_plan(subject), session, dry_run=True
        )

        session.execute.assert_not_awaited()
        session.commit.assert_not_awaited()
        assert report.dry_run is True
        assert report.total_rows == 0

    @pytest.mark.asyncio
    async def test_real_run_executes_and_commits(self):
        session = MagicMock()
        result = MagicMock()
        result.rowcount = 2
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()

        subject = _full_subject()
        steps = build_erasure_plan(subject)
        report = await execute_plan(subject, steps, session, dry_run=False)

        writable = [s for s in steps if s.action is not Action.REVIEW]
        assert session.execute.await_count == len(writable)
        session.commit.assert_awaited_once()
        assert report.total_rows == 2 * len(writable)
        assert report.dry_run is False

    @pytest.mark.asyncio
    async def test_review_steps_are_reported_not_executed(self):
        session = MagicMock()
        result = MagicMock()
        result.rowcount = 0
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()

        subject = _full_subject()
        report = await execute_plan(
            subject, build_erasure_plan(subject), session, dry_run=False
        )

        reviewed = {item["table"] for item in report.manual_review}
        assert reviewed == {"operational_memory", "agent_action_log", "pms_sync_logs"}

    @pytest.mark.asyncio
    async def test_report_always_carries_the_caveats(self):
        session = MagicMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        subject = _full_subject()
        report = await execute_plan(subject, build_erasure_plan(subject), session, dry_run=True)
        assert BACKUP_CAVEAT in report.caveats
        assert FREE_TEXT_CAVEAT in report.caveats
