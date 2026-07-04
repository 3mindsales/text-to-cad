"""Locality classification — the code that protects the air-gap promise (I4).

A model is *local* (air-gapped-safe) only if it is an offline model served from
localhost. Two independent signals make a call NON-local:

    1. the model tag ends in ``-cloud`` (Ollama Cloud), or
    2. the host is not localhost / a loopback / an RFC-1918 private address.

Classification is deliberately CONSERVATIVE: anything we cannot positively prove is
local is treated as non-local. We never resolve hostnames over the network to make
this decision (that would itself leak / require connectivity), so an unknown hostname
is classified non-local. "It's still Ollama" does not make a `-cloud` tag air-gapped.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

_LOCAL_HOSTNAMES = {"localhost", "ip6-localhost", "ip6-loopback"}


def is_cloud_tag(model_tag: str | None) -> bool:
    """True if the model tag denotes an Ollama Cloud model (``*-cloud``)."""
    if not model_tag:
        return False
    return model_tag.strip().lower().endswith("-cloud")


def _extract_host(host: str) -> str:
    """Pull the bare hostname/IP out of a host string or URL.

    Accepts ``127.0.0.1``, ``127.0.0.1:11434``, ``localhost``,
    ``http://127.0.0.1:11434``, ``https://ollama.com/v1``, ``[::1]:11434``.
    """
    raw = (host or "").strip()
    if not raw:
        return ""
    # Add a scheme so urlparse populates .hostname consistently.
    parsed = urlparse(raw if "://" in raw else f"//{raw}", scheme="")
    hostname = parsed.hostname
    if hostname:
        return hostname
    # Fallback: strip a trailing :port from a bare host.
    return raw.split("/")[0].rsplit(":", 1)[0].strip("[]")


def is_local_host(host: str | None) -> bool:
    """True only if ``host`` is localhost, a loopback, or an RFC-1918 private IP.

    Hostnames other than the well-known local names are treated as non-local
    without DNS resolution (conservative, air-gap-safe).
    """
    if host is None:
        return False
    name = _extract_host(host).lower()
    if not name:
        return False
    if name in _LOCAL_HOSTNAMES:
        return True
    try:
        ip = ipaddress.ip_address(name)
    except ValueError:
        # Not a literal IP and not a known-local hostname -> treat as non-local.
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


def compute_is_local(host: str | None, model_tag: str | None) -> bool:
    """Combined gate: local only if the host is local AND the tag is not cloud."""
    return is_local_host(host) and not is_cloud_tag(model_tag)
