#!/usr/bin/env bash
# Pull latest code and restart the service.
# Run as root on the server.
set -euo pipefail

APP_DIR="/opt/qbank"
APP_USER="qbank"

echo "==> Pulling latest code..."
git -C "$APP_DIR" pull --ff-only

echo "==> Updating dependencies..."
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "==> Fixing ownership..."
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "==> Restarting service..."
systemctl restart qbank
echo "    Status: $(systemctl is-active qbank)"

echo "Done."
