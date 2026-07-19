#!/bin/bash
# First-boot bootstrap for the AITX agent host (Ubuntu 24.04).
# Installs Docker, clones the STABLE FORK, prepares the deploy stack, and
# schedules the July 20 backup+self-stop. Secrets (.env) are NOT baked in —
# they arrive via scp after provisioning (see infra/README.md step 4).
set -euxo pipefail
exec > /var/log/aitx-bootstrap.log 2>&1

apt-get update -q
apt-get install -y -q docker.io docker-compose-v2 git curl jq

# Gateway state dirs shared host<->workspace at identical paths (see compose)
mkdir -p /root/.local/state/nemoclaw /root/.local/state/openshell

# Clone the user's fork (more stable than upstream; public, no auth needed)
install -d -o ubuntu -g ubuntu /opt/aitx
sudo -u ubuntu git clone https://github.com/Tar-ive/AITX-SAT-2026.git /opt/aitx/repo || true
usermod -aG docker ubuntu

# The OpenShell gateway (inside the workspace container) launches the sandbox
# via the HOST docker daemon, bind-mounting /usr/local/bin/openshell-sandbox
# from the HOST at the identical path. Sync the binaries out of the workspace
# once they exist; guard runs every 2 minutes and is idempotent.
cat > /opt/aitx/sync-openshell-bins.sh <<'EOS'
#!/bin/bash
W=$(docker ps --format '{{.Names}}' | grep workspace | head -1)
[ -n "$W" ] || exit 0
for b in openshell openshell-gateway openshell-sandbox; do
  if [ ! -f "/usr/local/bin/$b" ]; then
    rm -rf "/usr/local/bin/$b"
    docker cp "$W:/usr/local/bin/$b" "/usr/local/bin/$b" 2>/dev/null && chmod 755 "/usr/local/bin/$b"
  fi
done
EOS
chmod 700 /opt/aitx/sync-openshell-bins.sh
echo "*/2 * * * * root /opt/aitx/sync-openshell-bins.sh" > /etc/cron.d/aitx-bin-sync

# Backup + self-stop script (July 20, 05:00 UTC == July 20, 00:00 CDT)
cat > /opt/aitx/backup-and-stop.sh <<'EOS'
#!/bin/bash
set -x
TS=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p /opt/aitx/backups
C=$(docker ps -a --format '{{.Names}}' | grep openshell- | head -1)
if [ -n "$C" ]; then
  docker cp "$C:/sandbox/.openclaw" "/opt/aitx/backups/openclaw-state-$TS" || true
  tar czf "/opt/aitx/backups/openclaw-state-$TS.tar.gz" -C /opt/aitx/backups "openclaw-state-$TS" && rm -rf "/opt/aitx/backups/openclaw-state-$TS"
fi
cp /opt/aitx/repo/deploy/docker-compose/.env "/opt/aitx/backups/env-$TS.bak" 2>/dev/null || true
sync
shutdown -h +2 "AITX 2-day lifetime reached; agents backed up to /opt/aitx/backups"
EOS
chmod 700 /opt/aitx/backup-and-stop.sh

cat > /etc/cron.d/aitx-selfstop <<'EOC'
0 5 20 7 * root /opt/aitx/backup-and-stop.sh
EOC

echo "bootstrap complete"
