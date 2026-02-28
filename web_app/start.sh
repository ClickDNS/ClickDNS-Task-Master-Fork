#!/bin/bash
# start.sh — Railway startup script
# Tailscale is pre-installed at build time via Dockerfile.

set -euo pipefail

if [ -n "${TAILSCALE_AUTH_KEY:-}" ]; then
    echo "[start] Fetching latest Tailscale version..."
    TAILSCALE_VERSION=$(curl -fsSL "https://api.github.com/repos/tailscale/tailscale/releases/latest" \
        | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'].lstrip('v'))")
    echo "[start] Installing Tailscale ${TAILSCALE_VERSION}..."

    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)  TS_ARCH="amd64" ;;
        aarch64) TS_ARCH="arm64" ;;
        armv7l)  TS_ARCH="arm"   ;;
        *)       echo "[start] Unsupported arch: $ARCH"; exit 1 ;;
    esac

    TS_PKG="tailscale_${TAILSCALE_VERSION}_${TS_ARCH}"
    TS_BIN="/tmp/ts-bin"
    mkdir -p "$TS_BIN"

    curl -fsSL -o /tmp/tailscale.tgz "https://pkgs.tailscale.com/stable/${TS_PKG}.tgz"
    tar -xzf /tmp/tailscale.tgz -C /tmp
    cp "/tmp/${TS_PKG}/tailscale"  "$TS_BIN/"
    cp "/tmp/${TS_PKG}/tailscaled" "$TS_BIN/"
    chmod +x "$TS_BIN/tailscale" "$TS_BIN/tailscaled"
    rm -rf "/tmp/${TS_PKG}" /tmp/tailscale.tgz
    export PATH="$TS_BIN:$PATH"

    echo "[start] Starting tailscaled in userspace mode..."
    mkdir -p /var/run/tailscale /var/lib/tailscale
    tailscaled \
        --tun=userspace-networking \
        --statedir=/var/lib/tailscale \
        --socket=/var/run/tailscale/tailscaled.sock \
        --outbound-http-proxy-listen=localhost:1055 \
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
        --advertise-tags=tag:ci \
        --shields-up

    echo "[start] Connected:"
    tailscale --socket=/var/run/tailscale/tailscaled.sock status
else
    echo "[start] No TAILSCALE_AUTH_KEY — skipping Tailscale."
fi

echo "[start] Starting gunicorn..."
if [ -n "${TAILSCALE_AUTH_KEY:-}" ]; then
    # Tell the Flask app to route koda-paste calls through tailscaled's outbound
    # HTTP proxy — required in userspace-networking mode where Tailscale IPs aren't
    # directly routable from the container.
    export KODA_PASTE_PROXY="http://localhost:1055"
fi
exec gunicorn app:app
