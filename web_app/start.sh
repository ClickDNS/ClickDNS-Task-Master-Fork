#!/bin/bash
# start.sh — Railway startup script
# Downloads Tailscale and connects to Tailnet (if TAILSCALE_AUTH_KEY is set),
# then starts the web app.

set -e

if [ -n "$TAILSCALE_AUTH_KEY" ]; then
    echo "[start] Tailscale auth key found — installing Tailscale..."

    # Download tailscale binaries at runtime (avoids nixpacks interference)
    TAILSCALE_VERSION="1.80.2"
    curl -fsSL "https://pkgs.tailscale.com/stable/tailscale_${TAILSCALE_VERSION}_amd64.tgz" \
        | tar -C /usr/local/bin --strip-components=1 -xz \
            "tailscale_${TAILSCALE_VERSION}_linux_amd64/tailscale" \
            "tailscale_${TAILSCALE_VERSION}_linux_amd64/tailscaled"

    echo "[start] Starting tailscaled in userspace mode..."
    mkdir -p /var/run/tailscale /var/lib/tailscale
    tailscaled \
        --tun=userspace-networking \
        --statedir=/var/lib/tailscale \
        --socket=/var/run/tailscale/tailscaled.sock \
        > /tmp/tailscaled.log 2>&1 &

    sleep 2

    echo "[start] Connecting to Tailnet..."
    tailscale --socket=/var/run/tailscale/tailscaled.sock up \
        --authkey="$TAILSCALE_AUTH_KEY" \
        --hostname="taskmaster-railway" \
        --accept-routes \
        --shields-up

    echo "[start] Tailscale connected:"
    tailscale --socket=/var/run/tailscale/tailscaled.sock status
else
    echo "[start] No TAILSCALE_AUTH_KEY — skipping Tailscale (koda-paste offload disabled)."
fi

echo "[start] Starting gunicorn..."
exec gunicorn app:app
