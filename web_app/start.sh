#!/bin/bash
# start.sh — Railway startup script
# Downloads Tailscale and connects to Tailnet (if TAILSCALE_AUTH_KEY is set),
# then starts the web app.

set -euo pipefail

if [ -n "${TAILSCALE_AUTH_KEY:-}" ]; then
    echo "[start] Tailscale auth key found — installing Tailscale..."

    TAILSCALE_VERSION="1.80.2"

    # Detect architecture
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)  TS_ARCH="amd64" ;;
        aarch64) TS_ARCH="arm64" ;;
        armv7l)  TS_ARCH="arm"   ;;
        *)       echo "[start] Unsupported arch: $ARCH"; exit 1 ;;
    esac
    echo "[start] Architecture: $ARCH → $TS_ARCH"

    TS_PKG="tailscale_${TAILSCALE_VERSION}_${TS_ARCH}"
    TS_BIN="/tmp/ts-bin"
    mkdir -p "$TS_BIN"

    # Download to file (don't pipe — easier to debug and avoids pipefail edge cases)
    echo "[start] Downloading ${TS_PKG}.tgz..."
    curl -fsSL -o /tmp/tailscale.tgz \
        "https://pkgs.tailscale.com/stable/${TS_PKG}.tgz"
    echo "[start] Download complete: $(du -sh /tmp/tailscale.tgz | cut -f1)"

    # Extract and copy binaries to /tmp (always writable)
    tar -xzf /tmp/tailscale.tgz -C /tmp
    cp "/tmp/${TS_PKG}/tailscale"  "$TS_BIN/"
    cp "/tmp/${TS_PKG}/tailscaled" "$TS_BIN/"
    chmod +x "$TS_BIN/tailscale" "$TS_BIN/tailscaled"
    rm -rf "/tmp/${TS_PKG}" /tmp/tailscale.tgz

    # Add to PATH for this session
    export PATH="$TS_BIN:$PATH"

    # Verify install (run directly, not in $() so set -e catches failure)
    echo -n "[start] Tailscale installed: "
    "$TS_BIN/tailscale" version --short

    echo "[start] Starting tailscaled in userspace mode..."
    mkdir -p /var/run/tailscale /var/lib/tailscale
    "$TS_BIN/tailscaled" \
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
    "$TS_BIN/tailscale" --socket=/var/run/tailscale/tailscaled.sock up \
        --authkey="$TAILSCALE_AUTH_KEY" \
        --hostname="taskmaster-railway" \
        --accept-routes \
        --shields-up

    echo "[start] Tailscale connected:"
    "$TS_BIN/tailscale" --socket=/var/run/tailscale/tailscaled.sock status
else
    echo "[start] No TAILSCALE_AUTH_KEY — skipping Tailscale (koda-paste offload disabled)."
fi

echo "[start] Starting gunicorn..."
exec gunicorn app:app
