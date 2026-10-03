#!/usr/bin/env bash
# Sets up nginx in front of the compose stack on a fresh Ubuntu host.
# Run as root:  sudo ./deploy/setup-nginx.sh
#
# TLS is terminated by Cloudflare, so this installs an origin certificate that only
# Cloudflare trusts. For a directly reachable origin, swap in a certbot certificate
# instead (see the note at the bottom).

set -euo pipefail

DOMAIN="${DOMAIN:-audio.example.com}"
CERT_DIR="${CERT_DIR:-/etc/ssl/gnani}"

if [[ $EUID -ne 0 ]]; then
    echo "Run this with sudo." >&2
    exit 1
fi

echo "==> Installing nginx"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx

echo "==> Installing the site configuration"
install -d -m 755 "$CERT_DIR"
sed "s/audio\.example\.com/$DOMAIN/g" "$(dirname "$0")/nginx.conf" > /etc/nginx/sites-available/gnani
ln -sf /etc/nginx/sites-available/gnani /etc/nginx/sites-enabled/gnani
rm -f /etc/nginx/sites-enabled/default

echo "==> Installing the Cloudflare origin certificate"
if [[ -f "$CERT_DIR/fullchain.pem" && -f "$CERT_DIR/privkey.pem" ]]; then
    echo "    already present at $CERT_DIR, leaving it alone"
else
    echo "    Generate one at https://dash.cloudflare.com/?to=/:account/ssl-tls/origin-ca"
    echo "    then copy both files into $CERT_DIR and re-run this script."
    # A self-signed placeholder keeps `nginx -t` meaningful while TLS is not set up.
    openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
        -subj "/CN=$DOMAIN" \
        -keyout "$CERT_DIR/privkey.pem" -out "$CERT_DIR/fullchain.pem" 2>/dev/null
    chmod 600 "$CERT_DIR/privkey.pem"
    echo "    placeholder certificate written. Replace it before serving traffic."
fi

echo "==> Reloading nginx"
nginx -t
systemctl enable --now nginx
systemctl reload nginx

echo "==> Opening the firewall"
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

echo
echo "Done. Check it:"
echo "  systemctl status nginx"
echo "  curl -I http://$DOMAIN/health"
echo
echo "For a directly reachable origin instead of Cloudflare, replace the certificate"
echo "with certbot:  certbot certonly --standalone -d $DOMAIN &&"
echo "  sed -i 's#/etc/ssl/gnani/fullchain.pem#/etc/letsencrypt/live/$DOMAIN/fullchain.pem#; s#/etc/ssl/gnani/privkey.pem#/etc/letsencrypt/live/$DOMAIN/privkey.pem#' /etc/nginx/sites-available/gnani"