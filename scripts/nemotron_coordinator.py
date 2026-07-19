#!/usr/bin/env python3
"""Compat shim — moved to nemoclaw/scripts/nemotron_coordinator.py.

Keeps external invokers working during the layout rollout (Railway UI
start-command overrides, host habits). Remove once every deploy target
references the new path.
"""
import os
import sys

NEW = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "nemoclaw", "scripts", "nemotron_coordinator.py",
)
os.execv(sys.executable, [sys.executable, NEW, *sys.argv[1:]])
