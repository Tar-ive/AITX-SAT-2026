# Invoked by Task Scheduler with a hidden PowerShell window.
# Keeping wsl.exe as a child of this process prevents a console window from
# appearing for each scheduled Hermes cron tick.

$ErrorActionPreference = 'Stop'
$wsl = Join-Path $env:WINDIR 'System32\wsl.exe'
$openShell = (& $wsl -d Ubuntu-24.04 -- bash -lc 'command -v openshell').Trim()
if (-not $openShell) { throw 'openshell is not installed in Ubuntu-24.04.' }

& $wsl -d Ubuntu-24.04 -- $openShell --gateway nemoclaw-8081 sandbox exec --name nemohermes-120b -- /opt/hermes/.venv/bin/hermes cron tick

# The proxy stores a new immutable SOUL version only when the file's SHA-256
# changes, so this lightweight sync is safe to run with the scheduler.
& $wsl -d Ubuntu-24.04 -- $openShell --gateway nemoclaw-8081 sandbox exec --name nemohermes-120b -- /opt/hermes/.venv/bin/python /sandbox/.hermes/skills/soul-version-sync/sync_soul_files.py
exit $LASTEXITCODE
