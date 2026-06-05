"""Eval-by-design tooling (ADR-0007 §5).

EVAL-0 (HOS-204) ships `validate_dataset.py` only. The per-layer runners
(`eval_forecast.py`, `eval_parser.py`, `eval_drift.py`, `eval_latency.py`,
`run_all.py`) land in EVAL-1…EVAL-5.
"""
