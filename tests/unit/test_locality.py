"""is_local() truth table — the permanent regression guard for the air-gap promise (I4).

If any of these flip, the air-gap guarantee is broken. Keep this suite forever.
"""

from __future__ import annotations

import pytest

from texttocad.llm.locality import compute_is_local, is_cloud_tag, is_local_host

LOCAL_MODEL = "qwen2.5-coder:7b-instruct"
CLOUD_MODEL = "qwen3-coder:480b-cloud"


@pytest.mark.parametrize(
    "host,tag,expected",
    [
        # Local host + local tag => LOCAL
        ("127.0.0.1:11434", LOCAL_MODEL, True),
        ("localhost", LOCAL_MODEL, True),
        ("http://127.0.0.1:11434", LOCAL_MODEL, True),
        ("192.168.1.50:11434", LOCAL_MODEL, True),
        ("10.0.0.3", LOCAL_MODEL, True),
        ("172.16.5.5", LOCAL_MODEL, True),
        ("[::1]:11434", LOCAL_MODEL, True),
        # Cloud tag on a local host => NON-LOCAL (the subtle one)
        ("127.0.0.1:11434", CLOUD_MODEL, False),
        ("localhost", "gpt-oss:120b-cloud", False),
        # Non-local host => NON-LOCAL regardless of tag
        ("ollama.com", LOCAL_MODEL, False),
        ("https://ollama.com/v1", LOCAL_MODEL, False),
        ("8.8.8.8", LOCAL_MODEL, False),
        ("api.example.com:443", LOCAL_MODEL, False),
        ("example.com:11434", LOCAL_MODEL, False),
    ],
)
def test_compute_is_local_truth_table(host, tag, expected):
    assert compute_is_local(host, tag) is expected


def test_is_cloud_tag():
    assert is_cloud_tag("qwen3-coder:480b-cloud") is True
    assert is_cloud_tag("gpt-oss:120b-CLOUD") is True
    assert is_cloud_tag("qwen2.5-coder:7b-instruct") is False
    assert is_cloud_tag(None) is False
    assert is_cloud_tag("") is False


def test_is_local_host_edges():
    assert is_local_host("127.0.0.1") is True
    assert is_local_host("169.254.1.1") is True  # link-local
    assert is_local_host("8.8.8.8") is False
    assert is_local_host("") is False
    assert is_local_host(None) is False
    # An unknown hostname must be treated as NON-local (conservative).
    assert is_local_host("some-internal-name") is False
