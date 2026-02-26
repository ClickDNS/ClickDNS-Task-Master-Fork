"""
Shared koda-paste upload utility.

Used by both the logging service (diff uploads) and modals (long description
storage). Descriptions exceeding DESCRIPTION_PASTE_THRESHOLD chars are uploaded
to koda-paste; the returned URL is stored in the database instead of the raw text.
"""
import json
import logging
import os
import socket
import time
from typing import Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)

# Descriptions longer than this are offloaded to koda-paste.
DESCRIPTION_PASTE_THRESHOLD = 500

_PASTE_URL = os.environ.get(
    "KODA_PASTE_URL", "https://koda-vps.tail9ac53b.ts.net:8844")
_PASTE_RETRY_AFTER = 0.0
_PASTE_DNS_BACKOFF_SECONDS = 300
_PASTE_FAILURE_BACKOFF_SECONDS = 120


def _paste_host_resolvable(hostname: str) -> bool:
    if not hostname:
        return False
    try:
        socket.getaddrinfo(hostname, None)
        return True
    except socket.gaierror:
        return False


def upload_to_paste(content: str, title: str = "Paste") -> Optional[str]:
    """Upload content to koda-paste and return the share URL, or None on failure.

    If the configured KODA_PASTE_URL uses a hostname that fails DNS, but a
    fallback IP (KODA_PASTE_FALLBACK_IP) is configured, attempt the upload
    against the fallback IP (keeps the same scheme and port).
    """
    global _PASTE_RETRY_AFTER

    now = time.time()
    if now < _PASTE_RETRY_AFTER:
        return None

    parsed_url = urlparse(_PASTE_URL)
    if not parsed_url.scheme or not parsed_url.netloc:
        logger.warning(f"Invalid KODA_PASTE_URL configured: {_PASTE_URL}")
        _PASTE_RETRY_AFTER = now + _PASTE_FAILURE_BACKOFF_SECONDS
        return None

    host = parsed_url.hostname or ""
    port = parsed_url.port

    # If hostname is not resolvable, optionally try a fallback IP from env
    if not _paste_host_resolvable(host):
        fallback_ip = os.environ.get("KODA_PASTE_FALLBACK_IP") or os.environ.get("KODA_PASTE_IP")
        if fallback_ip:
            logger.info(f"koda-paste hostname '{host}' not resolvable — attempting fallback to IP {fallback_ip}")
            # Build a fallback base URL keeping scheme and port
            netloc = f"{fallback_ip}:{port}" if port else fallback_ip
            fallback_base = f"{parsed_url.scheme}://{netloc}"
            try:
                payload = json.dumps({"content": content, "title": title}).encode()
                req = Request(
                    f"{fallback_base}/api/paste",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(req, timeout=5) as resp:
                    result = json.loads(resp.read().decode())
                    # Return full URL using the original paste ID path produced by server
                    url = result.get("url")
                    if url and url.startswith("/"):
                        # server returned a relative path — make absolute against fallback_base
                        return fallback_base.rstrip("/") + url
                    return url
            except (URLError, OSError, json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to upload to koda-paste via fallback IP {fallback_ip}: {e}")
                _PASTE_RETRY_AFTER = now + _PASTE_FAILURE_BACKOFF_SECONDS
                return None

        logger.warning(
            f"koda-paste DNS lookup failed for '{host}' — "
            "ensure KODA_PASTE_URL is reachable from this host or set KODA_PASTE_FALLBACK_IP"
        )
        _PASTE_RETRY_AFTER = now + _PASTE_DNS_BACKOFF_SECONDS
        return None

    # Host is resolvable — try the configured URL
    try:
        payload = json.dumps({"content": content, "title": title}).encode()
        req = Request(
            f"{_PASTE_URL}/api/paste",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode())
            return result.get("url")
    except (URLError, OSError, json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to upload to koda-paste: {e}")
        _PASTE_RETRY_AFTER = now + _PASTE_FAILURE_BACKOFF_SECONDS
        return None


def is_paste_url(value: str) -> bool:
    """Return True if the value looks like a koda-paste URL (stored description)."""
    paste_base = _PASTE_URL.rstrip("/")
    fallback_ip = os.environ.get("KODA_PASTE_FALLBACK_IP") or os.environ.get("KODA_PASTE_IP")
    if value.startswith(paste_base + "/p/"):
        return True
    if fallback_ip:
        # Accept pastes created via fallback base as well
        parsed = urlparse(_PASTE_URL)
        port = parsed.port
        netloc = f"{fallback_ip}:{port}" if port else fallback_ip
        fallback_base = f"{parsed.scheme}://{netloc}"
        return value.startswith(fallback_base + "/p/")
    return False


def offload_description(description: str, title: str = "Description") -> str:
    """
    If description exceeds DESCRIPTION_PASTE_THRESHOLD, upload to koda-paste
    and return the paste URL. Otherwise return the description unchanged.
    On paste failure, returns the original description (caller must handle
    the 1000-char modal limit separately if needed).
    """
    if len(description) <= DESCRIPTION_PASTE_THRESHOLD:
        return description

    paste_url = upload_to_paste(description, title=title)
    if paste_url:
        logger.info(f"Description offloaded to koda-paste: {paste_url}")
        return paste_url

    # Paste unavailable — return as-is (best effort)
    logger.warning("koda-paste unavailable; storing description inline (may exceed limits)")
    return description
