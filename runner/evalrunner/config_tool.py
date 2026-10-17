"""Normalise a config and compute its content-hash ID, for the API.

Usage:  echo '<config json>' | python -m evalrunner.config_tool
Prints {"id": ..., "config": <normalised>} or exits non-zero with the validation error.
"""

from __future__ import annotations

import json
import sys

from .harnesses import HARNESSES
from .schema import Config


def main() -> None:
    cfg = Config.from_dict(json.load(sys.stdin))
    if cfg.harness not in HARNESSES:
        sys.exit(f"unknown harness '{cfg.harness}'. Known: {sorted(HARNESSES)}")
    print(json.dumps({"id": cfg.config_id(), "config": cfg.to_dict()}))


if __name__ == "__main__":
    main()
