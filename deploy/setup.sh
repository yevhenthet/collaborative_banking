#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Question Bank — server bootstrap script
# Run once as root on a fresh Ubuntu 22.04 / 24.04 Hetzner server.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/yevhenthet/collaborative_banking/main/deploy/setup.sh | bash
#   — or —
#   bash deploy/setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO="https://github.com/yevhenthet/collaborative_banking.git"
APP_DIR="/opt/qbank"
APP_USER="qbank"

# ── 1. System packages ────────────────────────────────────────────────────────
echo "==> Installing system packages..."
apt-get update -q
apt-get install -y -q python3 python3-pip python3-venv git curl gnupg debian-keyring debian-archive-keyring apt-transport-https

# ── 2. Caddy ──────────────────────────────────────────────────────────────────
echo "==> Installing Caddy..."
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | tee /etc/apt/sources.list.d/caddy-stable.list > /dev/null
apt-get update -q
apt-get install -y -q caddy

# ── 3. App user ───────────────────────────────────────────────────────────────
echo "==> Creating system user '${APP_USER}'..."
id -u "$APP_USER" &>/dev/null || useradd -r -m -s /bin/bash "$APP_USER"

# ── 4. Clone repository ───────────────────────────────────────────────────────
echo "==> Cloning repository to ${APP_DIR}..."
if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" pull --ff-only
else
    git clone "$REPO" "$APP_DIR"
fi

# ── 5. Python virtual environment ─────────────────────────────────────────────
echo "==> Installing Python dependencies..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip -q
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt" -q

# ── 6. Generate .env ──────────────────────────────────────────────────────────
if [ ! -f "$APP_DIR/.env" ]; then
    echo "==> Generating .env..."
    SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
    cat > "$APP_DIR/.env" <<EOF
SESSION_SECRET_KEY=${SECRET}
HOST=127.0.0.1
PORT=8000
HTTPS_ONLY=true
EOF
    echo "    .env created. Edit ${APP_DIR}/.env if needed."
else
    echo "==> .env already exists — skipping."
fi

# ── 7. Fix ownership ──────────────────────────────────────────────────────────
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# ── 8. Install & start systemd service ───────────────────────────────────────
echo "==> Installing systemd service..."
cp "$APP_DIR/deploy/qbank.service" /etc/systemd/system/qbank.service
systemctl daemon-reload
systemctl enable qbank
systemctl restart qbank
echo "    Service status: $(systemctl is-active qbank)"

# ── 9. Configure Caddy ───────────────────────────────────────────────────────
echo "==> Installing Caddyfile..."
cp "$APP_DIR/deploy/Caddyfile" /etc/caddy/Caddyfile
echo ""
echo "  *** Edit /etc/caddy/Caddyfile and replace 'yourdomain.com' with your domain. ***"
echo "  Then run: systemctl reload caddy"
echo ""
systemctl enable caddy
systemctl start caddy

# ── Done ──────────────────────────────────────────────────────────────────────
echo "======================================================================"
echo " Question Bank deployed!"
echo ""
echo " Next steps:"
echo "   1. Edit /etc/caddy/Caddyfile — set your domain"
echo "      systemctl reload caddy"
echo ""
echo "   2. Create the first admin account:"
echo "      cd ${APP_DIR} && sudo -u ${APP_USER} venv/bin/python seed_admin.py"
echo ""
echo "   3. Open https://yourdomain.com"
echo "======================================================================"
