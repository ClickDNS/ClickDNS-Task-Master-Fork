#!/bin/bash
# start.sh — Railway startup script
# Connects to Tailscale (if TAILSCALE_AUTH_KEY is set) then starts the web app.

set -e

if [ -n "$TAILSCALE_AUTH_KEY" ]; then
    echo "[start] Tailscale auth key found — connecting to Tailnet..."

    # Start tailscaled in userspace networking mode (no root/TUN device needed)
    mkdir -p /var/run/tailscale /var/lib/tailscale
    tailscaled \
        --tun=userspace-networking \
        --statedir=/var/lib/tailscale \
        --socket=/var/run/tailscale/tailscaled.sock \
        > /tmp/tailscaled.log 2>&1 &

    TAILSCALED_PID=$!
    echo "[start] tailscaled started (PID $TAILSCALED_PID)"

    # Give tailscaled a moment to initialise
    sleep 2

    # Connect to the Tailnet
    tailscale --socket=/var/run/tailscale/tailscaled.sock up \
        --authkey="$TAILSCALE_AUTH_KEY" \
        --hostname="taskmaster-railway" \
        --accept-routes \
        --shields-up

    echo "[start] Tailscale connected."
    tailscale --socket=/var/run/tailscale/tailscaled.sock status
else
    echo "[start] No TAILSCALE_AUTH_KEY set — skipping Tailscale. koda-paste offload will be disabled."
fi

echo "[start] Starting gunicorn..."
exec gunicorn app:app
