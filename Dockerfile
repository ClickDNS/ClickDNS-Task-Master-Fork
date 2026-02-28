FROM python:3.12-slim

# curl + ca-certificates needed for Tailscale runtime install in start.sh
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY web_app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY web_app/ .

CMD ["bash", "start.sh"]
