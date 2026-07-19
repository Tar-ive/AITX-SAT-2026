#!/bin/bash
# First-boot bootstrap for the Cursor-autoresearch box. Installs Python, clones
# the fork (which carries the Karpathy-pattern loop), installs deps. Secrets
# (.env) arrive by scp after provisioning; the loop is started then.
set -euxo pipefail
exec > /var/log/cursor-bootstrap.log 2>&1

apt-get update -q
apt-get install -y -q python3-pip python3-venv git curl
pip3 install --break-system-packages -q requests 2>/dev/null || pip3 install -q requests

install -d -o ubuntu -g ubuntu /opt/aitx
sudo -u ubuntu git clone https://github.com/Tar-ive/AITX-SAT-2026.git /opt/aitx/repo || true

# July 20 self-stop (00:00 CDT == 05:00 UTC)
cat > /etc/cron.d/cursor-selfstop <<'EOC'
0 5 20 7 * root /sbin/shutdown -h now "AITX 2-day lifetime reached"
EOC

echo "cursor bootstrap complete"
