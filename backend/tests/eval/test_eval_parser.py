"""HOS-208 (EVAL-4) — parser metrics + confusion matrix + golden-set threshold."""
from __future__ import annotations

from scripts.eval.eval_parser import compute_parser_metrics, run
from scripts.eval.fake_intent_classifier import FakeIntentClassifier


def _sc(sid: str, intent: str, message: str) -> dict:
    return {
        "id": sid,
        "category": "parser_intent",
        "layer": "parser",
        "input": {"message": message, "language": "fr"},
        "expected": {"intent": intent},
    }


def test_confusion_matrix_and_accuracy():
    scenarios = [
        _sc("a", "accepted", "ok merci"),            # fake → accepted ✓
        _sc("b", "rejected", "non, pas d'accord"),   # fake → rejected ✓
        _sc("c", "modified", "covers: 80"),          # fake → modified ✓
        _sc("d", "accepted", "non merci"),           # fake → rejected ✗ (true accepted)
    ]
    r = compute_parser_metrics(scenarios, FakeIntentClassifier())

    assert r["n"] == 4
    assert r["accuracy"] == 0.75  # 3 / 4
    cm = r["confusion_matrix"]
    assert cm["accepted"]["accepted"] == 1
    assert cm["accepted"]["rejected"] == 1     # the misclassified "non merci"
    assert cm["rejected"]["rejected"] == 1
    assert cm["modified"]["modified"] == 1
    assert r["per_intent"]["modified"]["precision"] == 1.0
    assert r["per_intent"]["accepted"]["recall"] == 0.5  # 1 of 2 true-accepted caught


def test_skips_non_classification_scenarios():
    scenarios = [
        _sc("a", "accepted", "ok merci"),
        {"id": "ood", "category": "ood_edge", "layer": "parser",
         "input": {"message": "こんにちは"}, "expected": {"abstention": True}},
    ]
    r = compute_parser_metrics(scenarios, FakeIntentClassifier())
    assert r["n"] == 1  # the abstention/ood scenario is excluded


def test_run_on_golden_dataset_meets_threshold():
    """The deterministic fake classifies the curated golden set correctly,
    so the CI pipeline runs green (>= 90% gate). Real quality = nightly."""
    r = run()
    assert r["n"] >= 15
    assert r["accuracy"] >= 0.9
    # balanced matrix: each intent has >= 5 supporting scenarios
    for intent in ("accepted", "rejected", "modified"):
        assert r["per_intent"][intent]["support"] >= 5
