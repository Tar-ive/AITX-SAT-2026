#!/usr/bin/env python3
"""Compat shim — moved to autoresearch/scripts/auto_research_loop.py.

Keeps external invokers working during the layout rollout (docker-compose
services started from an older compose file, host habits). Remove once every
host runs the new compose file.
"""
import os
import sys

NEW = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "autoresearch", "scripts", "auto_research_loop.py",
)
os.execv(sys.executable, [sys.executable, NEW, *sys.argv[1:]])
