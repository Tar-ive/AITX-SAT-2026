#!/usr/bin/env python3
"""Autoresearch git workspace management.

Outputs shell commands (agent mode) or executes them (--exec / Python API).

Usage:
    python workspace.py init <workspace_dir> [--exec]
    python workspace.py branch <workspace_dir> <exp_id> <short_description> [--exec]
    python workspace.py branch-name <exp_id> <description>
    python workspace.py diff <workspace_dir> [--exec]
    python workspace.py merge <workspace_dir> <exp_id> <short_description> <commit_message> [--exec]
    python workspace.py revert <workspace_dir> <exp_id> <short_description> [--exec]
    python workspace.py log <workspace_dir> [--oneline] [--exec]
    python workspace.py current-branch <workspace_dir> [--exec]
    python workspace.py write-file <workspace_dir> <rel_path> <content_via_stdin> [--exec]
"""
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


def _safe_branch_name(exp_id, desc):
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", desc.lower())
    safe = re.sub(r"_+", "_", safe)[:40].rstrip("_")
    return f"exp_{exp_id}_{safe}"


def _cmds(workspace_dir, commands, execute=False):
    results = []
    if execute:
        for cmd in commands:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            results.append({
                "cmd": cmd,
                "returncode": r.returncode,
                "stdout": r.stdout[-2000:],
                "stderr": r.stderr[-1000:],
            })
            if r.returncode != 0:
                print(json.dumps({
                    "workspace": workspace_dir,
                    "ok": False,
                    "commands": commands,
                    "results": results,
                    "error": f"command failed ({r.returncode}): {cmd}",
                }, indent=2))
                sys.exit(1)
        print(json.dumps({
            "workspace": workspace_dir,
            "ok": True,
            "commands": commands,
            "results": results,
        }, indent=2))
        return
    print(json.dumps({"workspace": workspace_dir, "commands": commands}, indent=2))


def init(d, execute=False):
    qd = shlex.quote(d)
    os.makedirs(d, exist_ok=True)
    _cmds(d, [
        f"cd {qd} && git init --initial-branch=main 2>/dev/null || "
        f"(cd {qd} && git init && cd {qd} && git checkout -b main)",
        f"cd {qd} && git config user.email 'autoresearch@aitx'",
        f"cd {qd} && git config user.name 'autoresearch'",
        f"cd {qd} && git commit --allow-empty -m 'init autoresearch workspace'",
    ], execute=execute)


def branch(d, eid, desc, execute=False):
    qd = shlex.quote(d)
    b = _safe_branch_name(eid, desc)
    _cmds(d, [
        f"cd {qd} && git checkout main",
        f"cd {qd} && git checkout -b {b}",
    ], execute=execute)


def diff(d, execute=False):
    qd = shlex.quote(d)
    if execute:
        r = subprocess.run(
            f"cd {qd} && git diff main",
            shell=True, capture_output=True, text=True,
        )
        print(json.dumps({
            "workspace": d,
            "diff": r.stdout,
            "returncode": r.returncode,
        }, indent=2))
        return
    _cmds(d, [f"cd {qd} && git diff main"])


def merge(d, eid, desc, msg, execute=False):
    qd = shlex.quote(d)
    b = _safe_branch_name(eid, desc)
    qmsg = shlex.quote(msg)
    _cmds(d, [
        f"cd {qd} && git add -A",
        f"cd {qd} && git commit -m {qmsg} --allow-empty",
        f"cd {qd} && git checkout main",
        f"cd {qd} && git merge {b} --no-edit",
        f"cd {qd} && git branch -d {b}",
    ], execute=execute)


def revert(d, eid, desc, execute=False):
    qd = shlex.quote(d)
    b = _safe_branch_name(eid, desc)
    _cmds(d, [
        f"cd {qd} && git checkout -f main",
        f"cd {qd} && git branch -D {b}",
    ], execute=execute)


def write_file(d, rel_path, content, execute=False):
    """Write a file inside the workspace (used by the policy loop)."""
    path = Path(d) / rel_path
    if execute:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        print(json.dumps({"workspace": d, "path": str(path), "ok": True}, indent=2))
        return
    qd = shlex.quote(d)
    qp = shlex.quote(rel_path)
    # Content is written by the caller; we only emit a placeholder hint.
    _cmds(d, [f"cd {qd} && # write {qp} then git add"])


# --- Python API for auto_research_loop (no CLI indirection) ---

def run_git(workspace_dir, *args, check=True):
    r = subprocess.run(
        ["git", "-C", workspace_dir, *args],
        capture_output=True, text=True,
    )
    if check and r.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}"
        )
    return r


def ensure_workspace(workspace_dir, initial_files=None):
    """Create a git workspace with main branch; optionally seed files."""
    ws = Path(workspace_dir)
    ws.mkdir(parents=True, exist_ok=True)
    if not (ws / ".git").exists():
        run_git(str(ws), "init", "--initial-branch=main", check=False)
        if not (ws / ".git").exists():
            run_git(str(ws), "init")
            run_git(str(ws), "checkout", "-b", "main", check=False)
        run_git(str(ws), "config", "user.email", "autoresearch@aitx")
        run_git(str(ws), "config", "user.name", "autoresearch")
        run_git(str(ws), "commit", "--allow-empty", "-m", "init autoresearch workspace")
    if initial_files:
        for rel, content in initial_files.items():
            p = ws / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                p.write_text(content)
        run_git(str(ws), "add", "-A")
        # Commit only if there is something to commit
        status = run_git(str(ws), "status", "--porcelain", check=False)
        if status.stdout.strip():
            run_git(str(ws), "commit", "-m", "initial skeleton")
    return str(ws)


def start_experiment(workspace_dir, exp_id, desc):
    name = _safe_branch_name(exp_id, desc)
    run_git(workspace_dir, "checkout", "main")
    run_git(workspace_dir, "checkout", "-b", name)
    return name


def commit_and_merge(workspace_dir, exp_id, desc, message):
    name = _safe_branch_name(exp_id, desc)
    run_git(workspace_dir, "add", "-A")
    run_git(workspace_dir, "commit", "-m", message, "--allow-empty")
    run_git(workspace_dir, "checkout", "main")
    run_git(workspace_dir, "merge", name, "--no-edit")
    run_git(workspace_dir, "branch", "-d", name)
    return name


def discard_experiment(workspace_dir, exp_id, desc):
    name = _safe_branch_name(exp_id, desc)
    run_git(workspace_dir, "checkout", "-f", "main")
    run_git(workspace_dir, "branch", "-D", name, check=False)
    return name


def read_main_file(workspace_dir, rel_path):
    p = Path(workspace_dir) / rel_path
    # Ensure we read from main tip when on an experiment branch that may differ
    r = run_git(workspace_dir, "show", f"main:{rel_path}", check=False)
    if r.returncode == 0:
        return r.stdout
    return p.read_text() if p.exists() else ""


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    execute = "--exec" in args
    args = [a for a in args if a != "--exec"]
    cmd = args[0]
    if cmd == "init":
        init(args[1], execute=execute)
    elif cmd == "branch":
        branch(args[1], int(args[2]), args[3], execute=execute)
    elif cmd == "branch-name":
        print(_safe_branch_name(int(args[1]), args[2]))
    elif cmd == "diff":
        diff(args[1], execute=execute)
    elif cmd == "merge":
        merge(args[1], int(args[2]), args[3], args[4], execute=execute)
    elif cmd == "revert":
        revert(args[1], int(args[2]), args[3], execute=execute)
    elif cmd == "log":
        qd = shlex.quote(args[1])
        _cmds(args[1], [
            f"cd {qd} && git log{' --oneline' if '--oneline' in args else ''} -20"
        ], execute=execute)
    elif cmd == "current-branch":
        qd = shlex.quote(args[1])
        _cmds(args[1], [f"cd {qd} && git branch --show-current"], execute=execute)
    else:
        print(f"Unknown: {cmd}")
        sys.exit(1)
