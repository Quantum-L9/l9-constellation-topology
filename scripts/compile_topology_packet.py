#!/usr/bin/env python3
"""Standalone wrapper for the canonical compile-packet CLI command."""

from __future__ import annotations

import sys

from l9_constellation_topology.cli import run

if __name__ == "__main__":
    raise SystemExit(run(["compile-packet", *sys.argv[1:]]))
