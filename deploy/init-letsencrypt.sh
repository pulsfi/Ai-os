#!/usr/bin/env bash
# One-time HTTPS bootstrap for the OS AI stack.
#
# Solves the chicken-and-egg problem: nginx won't start without a cert, but
# certbot needs nginx serving :80 to prove domain ownership. We drop in a
# temporary self-signed cert, start nginx, swap it for a real Let's Encrypt
# cert, then reload. Run this ONCE after DNS points at the server.
#
#   cd /opt/os-ai && ./deploy/init-letsencrypt.sh you@email.com
set -euo pipefail

COMPOSE="docker compose -f docker-compose.prod.yml"
EMAIL="${1:-}"
[ -f .env ] || { echo "Missing .env (copy .env.prod.example -> .env first)"; exit 1; }
DOMAIN="$(grep -E '^DOMAIN=' .env | cut -d= -f2- | tr -d '"')"
[ -n "$DOMAIN" ] || { echo "DOMAIN not set in .env"; exit 1; }
[ -n "$EMAIL" ]  || { echo "Usage: ./deploy/init-letsencrypt.sh you@email.com"; exit 1; }

CERT_PATH="/etc/letsencrypt/live/$DOMAIN"
echo "==> Bootstrapping HTTPS for $DOMAIN"

# 1) Temporary self-signed cert so nginx can start.
$COMPOSE run --rm --entrypoint "/bin/sh -c '\
  mkdir -p $CERT_PATH && \
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout $CERT_PATH/privkey.pem -out $CERT_PATH/fullchain.pem \
    -subj /CN=$DOMAIN'" certbot

# 2) Bring up the proxy (and the app) with that dummy cert.
$COMPOSE up -d --build

# 3) Replace the dummy with a real cert.
echo "==> Requesting Let's Encrypt certificate"
$COMPOSE run --rm --entrypoint "/bin/sh -c '\
  rm -rf $CERT_PATH && \
  certbot certonly --webroot -w /var/www/certbot \
    -d $DOMAIN --email $EMAIL --agree-tos --no-eff-email --non-interactive'" certbot

# 4) Reload nginx to pick up the real cert.
$COMPOSE exec nginx nginx -s reload
echo "==> Done. Visit https://$DOMAIN"
