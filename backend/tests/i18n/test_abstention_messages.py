"""BLOCKING coverage test for abstention i18n (HOS-206 AC4 / PM caveat).

Fails if any reason is missing an FR or EN string, if any string is empty, or
if any manager-facing string leaks a raw enum code. The whole point of the i18n
layer is that a hotel manager never sees `cold_start_no_cohort` & co.
"""
from __future__ import annotations

import pytest

from app.i18n.abstention_messages import _MESSAGES, localized_message, messages_for_reason
from app.services.abstention import ABSTENTION_REASONS


def test_mapping_covers_exactly_the_reason_set():
    assert set(_MESSAGES) == set(ABSTENTION_REASONS)


@pytest.mark.parametrize("reason", ABSTENTION_REASONS)
def test_fr_and_en_present_and_nonempty(reason):
    m = messages_for_reason(reason)
    assert m.fr.strip(), f"empty FR for {reason}"
    assert m.en.strip(), f"empty EN for {reason}"


@pytest.mark.parametrize("reason", ABSTENTION_REASONS)
def test_no_raw_enum_code_leaks(reason):
    m = messages_for_reason(reason)
    for code in ABSTENTION_REASONS:
        assert code not in m.fr, f"raw code {code!r} leaked into FR[{reason}]"
        assert code not in m.en, f"raw code {code!r} leaked into EN[{reason}]"


def test_exactly_14_strings():
    assert sum(len(v) for v in _MESSAGES.values()) == 14  # 7 reasons × {fr, en}


def test_locale_resolution_defaults_to_fr():
    assert localized_message("cold_start_no_cohort") == messages_for_reason("cold_start_no_cohort").fr
    assert localized_message("cold_start_no_cohort", "en") == messages_for_reason("cold_start_no_cohort").en
    assert localized_message("cold_start_no_cohort", None) == messages_for_reason("cold_start_no_cohort").fr
