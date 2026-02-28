#!/bin/bash
# start.sh — Railway startup script
# Tailscale is pre-installed at build time via Dockerfile.

set -euo pipefail

if [ -n "${TAILSCALE_AUTH_KEY:-}" ]; then
    echo "[start] Starting tailscaled in userspace mode..."
    mkdir -p /var/run/tailscale /var/lib/tailscale
    tailscaled \
        --tun=userspace-networking \
        --statedir=/var/lib/tailscale \
        --socket=/var/run/tailscale/tailscaled.sock \
        > /tmp/tailscaled.log 2>&1 &
    TAILSCALED_PID=$!

    # Wait for socket (up to 10s)
    for i in $(seq 1 10); do
        [ -S /var/run/tailscale/tailscaled.sock ] && break
        if ! kill -0 "$TAILSCALED_PID" 2>/dev/null; then
            echo "[start] tailscaled crashed — log:"
            cat /tmp/tailscaled.log || true
            exit 1
        fi
        sleep 1
    done

    if [ ! -S /var/run/tailscale/tailscaled.sock ]; then
        echo "[start] tailscaled socket never appeared — log:"
        cat /tmp/tailscaled.log || true
        exit 1
    fi

    echo "[start] Connecting to Tailnet..."
    tailscale --socket=/var/run/tailscale/tailscaled.sock up \
        --authkey="$TAILSCALE_AUTH_KEY" \
        --hostname="taskmaster-railway" \
        --accept-routes \
        --shields-up

    echo "[start] Connected:"
    tailscale --socket=/var/run/tailscale/tailscaled.sock status
else
    echo "[start] No TAILSCALE_AUTH_KEY — skipping Tailscale."
fi

echo "[start] Starting gunicorn..."
exec gunicorn app:app
