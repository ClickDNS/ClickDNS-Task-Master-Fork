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
    """Upload content to koda-paste and return the share URL, or None on failure."""
    global _PASTE_RETRY_AFTER

    now = time.time()
    if now < _PASTE_RETRY_AFTER:
        return None

    parsed_url = urlparse(_PASTE_URL)
    if not parsed_url.scheme or not parsed_url.netloc:
        logger.warning(f"Invalid KODA_PASTE_URL configured: {_PASTE_URL}")
        _PASTE_RETRY_AFTER = now + _PASTE_FAILURE_BACKOFF_SECONDS
        return None

    # Only use the configured KODA_PASTE_URL (no fallback). If the host is
    # not resolvable we fail early and set backoff; the operator should set
    # KODA_PASTE_URL to an IP if they prefer to avoid DNS.
    if not _paste_host_resolvable(parsed_url.hostname or ""):
        logger.warning(
            f"koda-paste DNS lookup failed for '{parsed_url.hostname}' — "
            "ensure KODA_PASTE_URL is reachable from this host (use an IP if needed)"
        )
        _PASTE_RETRY_AFTER = now + _PASTE_DNS_BACKOFF_SECONDS
        return None

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
    return value.startswith(paste_base + "/p/")


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
