"""The landing's memory guard must give up, loudly, instead of waiting forever.

2026-10-31: the nightly refresh sat 8.5 h on 22 s of CPU after wam-desktop landed,
and systemd killed it. ArangoDB does not give memory back while idle, so a guard
that waits for it to fall below the limit can wait for ever, in silence.
"""

import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "land_full_corpus", Path(__file__).parents[2] / "scripts" / "land_full_corpus.py")
lfc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lfc)


def test_below_the_limit_it_does_not_wait():
    def never(_):
        pytest.fail("slept while below the limit")
    assert lfc.hold_while_above(lambda: 1, limit=2, max_seconds=60, sleep=never) == 0


def test_it_waits_until_memory_falls():
    readings = iter([5, 5, 1])
    slept = []
    paused = lfc.hold_while_above(lambda: next(readings), limit=2, max_seconds=600,
                                  sleep=slept.append, step=30)
    assert paused == 60
    assert slept == [30, 30]


def test_it_gives_up_at_the_deadline():
    slept = []
    with pytest.raises(TimeoutError, match="above"):
        lfc.hold_while_above(lambda: 5, limit=2, max_seconds=90, sleep=slept.append, step=30)
    assert sum(slept) == 90
