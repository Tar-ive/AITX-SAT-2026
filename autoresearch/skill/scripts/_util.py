#!/usr/bin/env python3
"""Shared utilities for autoresearch helper scripts."""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def autoresearch_home():
    """Root for run state and registry.

    Precedence: AUTORESEARCH_HOME → HERMES_HOME/autoresearch parent →
    <repo>/research. Repo is inferred from this file's location
    (skills/autoresearch/scripts/_util.py → repo root).
    """
    if os.environ.get("AUTORESEARCH_HOME"):
        return os.environ["AUTORESEARCH_HOME"]
    if os.environ.get("HERMES_HOME"):
        return os.path.join(os.environ["HERMES_HOME"], "autoresearch")
    repo = Path(__file__).resolve().parents[3]
    return str(repo / "research")


def hermes_home():
    """Back-compat alias used by registry/usage scripts."""
    if os.environ.get("HERMES_HOME"):
        return os.environ["HERMES_HOME"]
    # Treat the autoresearch parent as a synthetic Hermes home.
    home = Path(autoresearch_home())
    if home.name == "autoresearch":
        return str(home.parent)
    return str(home)


def atomic_write(path, data):
    """Write JSON data atomically via tempfile + os.replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, str(path))
    except Exception:
        os.unlink(tmp)
        raise


def read_json(path):
    """Read a JSON file, returning {} on missing/corrupt files."""
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
