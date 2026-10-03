#!/usr/bin/env bash
# Puts nginx (:80, plain HTTP) in front of the compose stack on Amazon Linux 2023.
# Run as root:  sudo ./deploy/setup-nginx.sh
#
# This installs deploy/nginx-http.conf, the pre-TLS phase. The TLS design in
# deploy/nginx.conf (443 + Cloudflare origin certificate) belongs to the later
# Cloudflare phase and is not installed here.

set -euo pipefail

CONF_SRC="$(dirname "$0")/nginx-http.conf"
CONF_DST="/etc/nginx/conf.d/gnani.conf"

if [[ $EUID -ne 0 ]]; then
    echo "Run this with sudo." >&2
    exit 1
fi

echo "==> Installing nginx"
dnf install -y nginx

echo "==> Installing the site configuration"
install -m 644 "$CONF_SRC" "$CONF_DST"

echo "==> Disabling the stock default server"
# AL2023 ships a default_server on :80 inside nginx.conf that would swallow
# every request before conf.d is read. Ours becomes the only listener.
sed -i 's/listen\(.*\)80 default_server/listen\1 80/' /etc/nginx/nginx.conf

echo "==> Reloading nginx"
nginx -t
systemctl enable --now nginx
systemctl reload nginx

cat <<'EOF'

Done. Filtering lives in the security group (AL2023 runs no host firewall);
it must allow 22/tcp from your IP only and 80/tcp from the world.
Check it:
  systemctl status nginx
  curl -I http://localhost/
EOF
