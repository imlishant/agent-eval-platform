"""Harness registry. Adding a harness = one class + one line here."""

from .base import HarnessAdapter
from .baseline import BaselineHarness
from .hermes import HermesHarness
from .mock import MockHarness

HARNESSES: dict[str, type[HarnessAdapter]] = {
    MockHarness.id: MockHarness,
    BaselineHarness.id: BaselineHarness,
    HermesHarness.id: HermesHarness,
}


def get_harness(harness_id: str) -> HarnessAdapter:
    if harness_id not in HARNESSES:
        raise ValueError(f"unknown harness '{harness_id}'. Known: {sorted(HARNESSES)}")
    return HARNESSES[harness_id]()
