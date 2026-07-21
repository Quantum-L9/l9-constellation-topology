#!/usr/bin/env python3
"""Standalone wrapper for lazy report rendering."""

from __future__ import annotations

import sys

from l9_constellation_topology.cli import run

if __name__ == "__main__":
    raise SystemExit(run(["render-report", *sys.argv[1:]]))
