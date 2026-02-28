#!/bin/bash
# start.sh — Railway startup script
# Downloads Tailscale and connects to Tailnet (if TAILSCALE_AUTH_KEY is set),
# then starts the web app.

set -euo pipefail

if [ -n "${TAILSCALE_AUTH_KEY:-}" ]; then
    echo "[start] Tailscale auth key found — installing Tailscale..."

    # Download tailscale binaries at runtime (avoids nixpacks interference)
    TAILSCALE_VERSION="1.80.2"
    TAILSCALE_DIR="tailscale_${TAILSCALE_VERSION}_amd64"
    TMPDIR=$(mktemp -d)

    curl -fsSL "https://pkgs.tailscale.com/stable/${TAILSCALE_DIR}.tgz" \
        | tar -C "$TMPDIR" -xz

    install -m 755 "$TMPDIR/${TAILSCALE_DIR}/tailscale"  /usr/local/bin/tailscale
    install -m 755 "$TMPDIR/${TAILSCALE_DIR}/tailscaled" /usr/local/bin/tailscaled
    rm -rf "$TMPDIR"

    echo "[start] Tailscale installed: $(tailscale version)"

    echo "[start] Starting tailscaled in userspace mode..."
    mkdir -p /var/run/tailscale /var/lib/tailscale
    tailscaled \
        --tun=userspace-networking \
        --statedir=/var/lib/tailscale \
        --socket=/var/run/tailscale/tailscaled.sock \
        > /tmp/tailscaled.log 2>&1 &
    TAILSCALED_PID=$!

    # Wait for tailscaled socket to be ready (up to 10s)
    for i in $(seq 1 10); do
        if [ -S /var/run/tailscale/tailscaled.sock ]; then
            break
        fi
        if ! kill -0 "$TAILSCALED_PID" 2>/dev/null; then
            echo "[start] tailscaled crashed — check /tmp/tailscaled.log:"
            cat /tmp/tailscaled.log || true
            exit 1
        fi
        sleep 1
    done

    if [ ! -S /var/run/tailscale/tailscaled.sock ]; then
        echo "[start] tailscaled socket never appeared — check /tmp/tailscaled.log:"
        cat /tmp/tailscaled.log || true
        exit 1
    fi

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
