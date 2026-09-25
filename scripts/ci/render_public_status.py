#!/usr/bin/env python3
"""Render `public-status.yml` into the Markdown status block of the public meta-repo.

Deterministic, no LLM: the same file always renders the same bytes (entry order
= file order, no render timestamp), so an unchanged file never opens a PR.

Only `name`, `status`, `description` and `deployed` are rendered. `evidence` and
`id` never leave this repo. The rendered block is re-checked against the leak
denylist of check_public_status.py before it is returned — a second line of
defence if the renderer's own text ever drifts.

Exit codes:
  0  rendered / applied (with --apply: prints "changed" or "unchanged")
  1  public-status.yml invalid, or the rendered block would leak
  2  file missing or not parseable
  3  --apply target has no (or malformed) aetherix-status markers

Usage:
  python scripts/ci/render_public_status.py                  # block to stdout
  python scripts/ci/render_public_status.py --out block.md
  python scripts/ci/render_public_status.py --apply ../meta/README.md
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_public_status as gate  # noqa: E402

START_MARKER = "<!-- aetherix-status:start -->"
END_MARKER = "<!-- aetherix-status:end -->"

LIVE_LABELS = {True: "Yes", False: "No", "unknown": "Not verified", "n/a": "—"}


class MarkerError(ValueError):
    """The target document does not carry exactly one ordered marker pair."""


def _cell(text: str) -> str:
    """One table cell: single line, pipes escaped."""
    return " ".join(str(text).split()).replace("|", "\\|")


def _as_date(value: object) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def render(data: dict) -> str:
    """Return the Markdown block (without markers). `data` must already be valid."""
    entries = data["entries"]
    oldest = min(_as_date(e["verified_on"]) for e in entries)
    lines = [
        "<!-- Generated from the Aetherix node's public-status.yml. Do not edit by hand: the next sync overwrites it. -->",
        "",
        "| Capability | Status | What it does | Live? |",
        "|---|---|---|---|",
    ]
    for entry in entries:
        lines.append(
            f"| {_cell(entry['name'])} | **{_cell(entry['status'])}** | "
            f"{_cell(entry['description'])} | {LIVE_LABELS[entry['deployed']]} |"
        )
    lines += [
        "",
        "Reading this table: **Built** means merged on the node's main branch and covered by tests; "
        "it does not by itself mean deployed or used, and the node has zero real users. "
        "**Live?** is Yes only when the deployed version was checked, Not verified otherwise, "
        "and — for CI gates and eval harnesses. "
        f"Oldest entry verified on {oldest.isoformat()}.",
    ]
    block = "\n".join(lines) + "\n"
    leaks = gate.find_leaks(block)
    if leaks:
        raise ValueError(f"rendered block would leak: {leaks}")
    return block


def replace_block(document: str, block: str) -> str:
    """Replace the text between the markers (markers kept). Raises MarkerError."""
    if document.count(START_MARKER) != 1 or document.count(END_MARKER) != 1:
        raise MarkerError(
            f"expected exactly one {START_MARKER} and one {END_MARKER} "
            f"(found {document.count(START_MARKER)} and {document.count(END_MARKER)})"
        )
    start = document.index(START_MARKER) + len(START_MARKER)
    end = document.index(END_MARKER)
    if end < start:
        raise MarkerError(f"{END_MARKER} comes before {START_MARKER}")
    return document[:start] + "\n" + block + document[end:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", default=str(gate._ROOT / gate.DEFAULT_FILE))
    parser.add_argument("--root", default=str(gate._ROOT))
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--out", help="write the block to this file")
    group.add_argument("--apply", help="replace the marked block in this Markdown file, in place")
    args = parser.parse_args(argv)

    try:
        data = gate.load(Path(args.file))
    except (OSError, ValueError) as exc:
        print(f"❌ cannot read {args.file}: {exc}", file=sys.stderr)
        return 2

    root = Path(args.root)
    report = gate.validate(data, lambda p: (root / p).exists(), date.today())
    if not report.ok:
        for error in report.errors:
            print(f"::error title=public-status::{error}", file=sys.stderr)
        return 1

    try:
        block = render(data)
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if args.apply:
        target = Path(args.apply)
        before = target.read_text(encoding="utf-8")
        try:
            after = replace_block(before, block)
        except MarkerError as exc:
            print(f"❌ {target}: {exc}", file=sys.stderr)
            return 3
        if after == before:
            print("unchanged")
        else:
            target.write_text(after, encoding="utf-8")
            print("changed")
        return 0

    if args.out:
        Path(args.out).write_text(block, encoding="utf-8")
    else:
        sys.stdout.write(block)
    return 0


if __name__ == "__main__":
    sys.exit(main())
