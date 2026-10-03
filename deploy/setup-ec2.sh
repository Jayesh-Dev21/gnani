#!/usr/bin/env bash
# First-run setup for a fresh Amazon Linux 2023 EC2 instance running this app.
#   ./deploy/setup-ec2.sh
#
# The compose stack is the deployable unit: this script prepares the host and then
# hands over to `docker compose up -d --build`.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Jayesh-Dev21/gnani.git}"
APP_DIR="${APP_DIR:-/opt/gnani}"

echo "==> Docker"
if ! command -v docker >/dev/null; then
    dnf install -y docker
fi
systemctl enable --now docker
usermod -aG docker "${USER}"

echo "==> Log rotation"
# Containers log to stdout, so without this the disk fills up.
if [[ ! -f /etc/docker/daemon.json ]]; then
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
JSON
    systemctl restart docker
fi

echo "==> Swap"
# Postgres and the ASR worker both like having somewhere to spill when memory is tight.
if ! swapon --show | grep -q .; then
    fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
    grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> Application"
if [[ ! -d "$APP_DIR" ]]; then
    git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "    .env created. Fill in BETTER_AUTH_SECRET, GNANI_API_KEY, GROQ_API_KEY and the"
    echo "    R2 credentials, then run: docker compose up -d --build"
else
    docker compose up -d --build
fi

echo
echo "Next:"
echo "  cd $APP_DIR && nano .env && docker compose up -d --build"
echo "  sudo ./deploy/setup-nginx.sh"
echo "  docker compose logs -f worker"
echo
echo "Instance checklist that this script cannot do for you:"
echo "  - Security group: allow 22 from your IP only, plus 80 to the world."
echo "    Do not expose 5432 to the world; Postgres stays inside the compose network."
echo "  - Keep the 3000 and 8000 ports closed in the security group; nginx is the only"
echo "    way in. The published ports exist for local debugging."
echo "  - Set BETTER_AUTH_URL and BETTER_AUTH_TRUSTED_ORIGINS to http://the-host"
echo "    (https://that-domain once the Cloudflare phase adds TLS)."