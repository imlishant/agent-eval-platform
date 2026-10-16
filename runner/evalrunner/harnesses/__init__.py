"""Harness registry. Adding a harness = one class + one line here."""

from .base import HarnessAdapter
from .mock import MockHarness

HARNESSES: dict[str, type[HarnessAdapter]] = {
    MockHarness.id: MockHarness,
}


def get_harness(harness_id: str) -> HarnessAdapter:
    if harness_id not in HARNESSES:
        raise ValueError(f"unknown harness '{harness_id}'. Known: {sorted(HARNESSES)}")
    return HARNESSES[harness_id]()
