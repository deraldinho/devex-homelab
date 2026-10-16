"""CP-WEB-01: fail-closed static citation policy (no HTTP client).

Calling this does NOT perform a web search and does NOT make fetching a URL
safe. A future HTTP client must resolve DNS, block non-public IPs after each
redirect, constrain response bytes and enforce TLS independently.
"""
from __future__ import annotations

import ipaddress
import re
from urllib.parse import parse_qsl, urlsplit


class WebResearchDenied(ValueError):
    pass


_HOST = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")
_SECRET_KEYS = {"token", "access_token", "apikey", "api_key", "key",
                "auth", "authorization", "password", "secret", "session", "code"}


def _safe_text(value: str, limit: int) -> str:
    if not isinstance(value, str):
        raise WebResearchDenied("untrusted_text_not_string")
    escaped = []
    size = 0
    for char in value:
        if ord(char) < 32 or ord(char) == 127:
            continue
        token = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}.get(char, char)
        if size + len(token) > limit:
            break
        escaped.append(token)
        size += len(token)
    return "".join(escaped)


def validate_reference(url: str, title: str, snippet: str, allowed_hosts) -> dict:
    """Prepare a bounded, explicitly unverified, host-allowlisted citation.

    Strict exact-host matching: never allow by suffix, regex interpolation or
    arbitrary redirect. No network, credentials, filesystem or cookies.
    """
    if not isinstance(url, str) or not url or len(url) > 2048:
        raise WebResearchDenied("invalid_url")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in url):
        raise WebResearchDenied("control_character_in_url")
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError as exc:
        raise WebResearchDenied("invalid_url_structure") from exc
    if parsed.scheme.lower() != "https" or not host or parsed.username is not None or parsed.password is not None:
        raise WebResearchDenied("url_requires_https_host_without_credentials")
    if port not in (None, 443) or not _HOST.fullmatch(host):
        raise WebResearchDenied("unsupported_host_or_port")
    if host == "localhost" or host.endswith(".localhost"):
        raise WebResearchDenied("localhost_forbidden")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise WebResearchDenied("ip_literal_forbidden")
    try:
        approved = {str(item).lower().rstrip(".") for item in allowed_hosts}
    except (TypeError, ValueError) as exc:
        raise WebResearchDenied("invalid_host_allowlist") from exc
    if not approved or host not in approved:
        raise WebResearchDenied("host_not_approved")
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in _SECRET_KEYS:
            raise WebResearchDenied("secret_bearing_query")
    return {
        "url": url,
        "host": host,
        "title": _safe_text(title, 160),
        "snippet": _safe_text(snippet, 1500),
        "verified_by_network": False,
        "trust": "untrusted_external_reference",
    }
