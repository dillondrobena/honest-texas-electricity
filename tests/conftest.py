import json
import os

import pytest

from htx.models import Plan

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _load(name: str) -> list[Plan]:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return [Plan.from_dict(d) for d in json.load(fh)]


@pytest.fixture(scope="session")
def oncor_all() -> list[Plan]:
    """All 297 raw Oncor plans from the July snapshot."""
    return _load("oncor_all.json")


@pytest.fixture(scope="session")
def oncor_filtered() -> list[Plan]:
    """The 60 Oncor plans the curator kept."""
    return _load("oncor_filtered.json")


@pytest.fixture(scope="session")
def all_plans() -> list[Plan]:
    """All 1,652 plans across every region from the July snapshot."""
    return _load("all_plans.json")
