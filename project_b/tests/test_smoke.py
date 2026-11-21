"""Injector + detector sanity checks on synthetic clean data."""
import numpy as np
import pytest

from project_b.detectors.rules import RuleDetectors
from project_b.detectors.stats import StatDetectors
from project_b.injector.corruptions import BY_KEY, CORRUPTIONS, inject


def test_twelve_corruption_types():
    assert len(CORRUPTIONS) == 12
    assert sorted(BY_KEY) == list("abcdefghijkl")


@pytest.mark.parametrize("key", list("abcdefghijkl"))
def test_injection_is_seeded_and_changes_data(clean, key):
    a, ta = inject(clean, key, 0.1, seed=3)
    b, tb = inject(clean, key, 0.1, seed=3)
    assert a.equals(b)  # reproducible
    assert not (a.shape == clean.shape and a.equals(clean))  # something changed
    if ta.row_mask is not None:
        assert len(ta.row_mask) == len(a) and ta.n_bad_rows > 0


def test_clean_data_raises_no_rule_alerts(clean):
    rules = RuleDetectors().fit(clean)
    keys = {a.problem_key for a in rules.detect(clean)}
    assert keys == set(), keys


@pytest.mark.parametrize("key", list("abcdehil"))
def test_rules_catch_what_they_should(clean, key):
    rules = RuleDetectors().fit(clean)
    cb, truth = inject(clean, key, 0.1, seed=1)
    alerts = [a for a in rules.detect(cb) if a.problem_key == key]
    assert alerts, f"rules missed problem {key}"
    if truth.row_mask is not None:
        flagged = {a.row_index for a in alerts}
        bad = set(np.flatnonzero(truth.row_mask).tolist())
        assert len(flagged & bad) / len(bad) > 0.8


def test_stats_fit_and_detect_run(clean):
    half = len(clean) // 2
    stats = StatDetectors().fit(clean.iloc[:half])
    cb, _ = inject(clean.iloc[half:].reset_index(drop=True), "d", 0.1, seed=0)
    assert any(a.problem_key == "d" for a in stats.detect(cb))


def test_alert_clarity_scoring():
    from project_b.detectors.base import Alert
    full = Alert("d", "x", "rules", "a long explanation", 1, "latitude", "-73.9", "40.5-40.9")
    bare = Alert("d", "x", "rules", "bad", 1)
    assert full.clarity() == 1.0 and bare.clarity() == 0.0
