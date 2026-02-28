FROM python:3.12-slim

# Install Tailscale at build time — no runtime download needed
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && \
    ARCH=$(dpkg --print-architecture) && \
    curl -fsSL "https://pkgs.tailscale.com/stable/tailscale_1.80.2_${ARCH}.tgz" -o /tmp/ts.tgz && \
    tar -xzf /tmp/ts.tgz -C /tmp && \
    mv /tmp/tailscale_1.80.2_${ARCH}/tailscale  /usr/local/bin/tailscale && \
    mv /tmp/tailscale_1.80.2_${ARCH}/tailscaled /usr/local/bin/tailscaled && \
    chmod +x /usr/local/bin/tailscale /usr/local/bin/tailscaled && \
    rm -rf /tmp/ts.tgz /tmp/tailscale_1.80.2_* && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY web_app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY web_app/ .

CMD ["bash", "start.sh"]
