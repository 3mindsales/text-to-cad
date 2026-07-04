"""Backend adapters: is_local classification + JSON round-trip via mocked transport.

No real network: the stdlib HTTP helpers are monkeypatched.
"""

from __future__ import annotations

import pytest

from texttocad.llm import _http
from texttocad.llm.anthropic_backend import AnthropicBackend
from texttocad.llm.llamacpp_backend import LlamaCppBackend
from texttocad.llm.ollama_backend import OllamaBackend
from texttocad.llm.openai_compat_backend import OpenAICompatibleBackend


def test_is_local_per_adapter():
    assert OllamaBackend("127.0.0.1:11434", "qwen2.5-coder:7b-instruct").is_local is True
    assert OllamaBackend("127.0.0.1:11434", "qwen3-coder:480b-cloud").is_local is False
    assert OllamaBackend("ollama.com", "qwen2.5-coder:7b-instruct").is_local is False
    assert LlamaCppBackend("model.gguf").is_local is True
    assert OpenAICompatibleBackend("http://127.0.0.1:1234/v1", "m").is_local is True
    assert OpenAICompatibleBackend("https://api.openai.com/v1", "gpt-4o").is_local is False
    assert AnthropicBackend().is_local is False


def test_ollama_generate_json_roundtrip(monkeypatch):
    def fake_post(url, payload, headers=None, timeout=120.0):
        assert "/api/chat" in url
        assert payload["format"] == "json"
        assert payload["options"]["temperature"] == 0
        return {
            "message": {"content": '{"mode":"template","part_type":"FLAT_PLATE","parameters":{"length":100}}'}
        }

    monkeypatch.setattr(_http, "post_json", fake_post)
    out = OllamaBackend().generate_json("sys", "flat plate 100")
    assert out["part_type"] == "FLAT_PLATE"
    assert out["parameters"]["length"] == 100


def test_ollama_generate_text(monkeypatch):
    monkeypatch.setattr(_http, "post_json", lambda *a, **k: {"message": {"content": "hello"}})
    assert OllamaBackend().generate_text("sys", "hi") == "hello"


def test_ollama_is_available(monkeypatch):
    monkeypatch.setattr(
        _http, "get_json", lambda *a, **k: {"models": [{"name": "qwen2.5-coder:7b-instruct"}]}
    )
    assert OllamaBackend(model_tag="qwen2.5-coder:7b-instruct").is_available() is True

    def boom(*a, **k):
        raise _http.HTTPError("refused")

    monkeypatch.setattr(_http, "get_json", boom)
    assert OllamaBackend().is_available() is False


def test_openai_compat_json(monkeypatch):
    monkeypatch.setattr(
        _http,
        "post_json",
        lambda *a, **k: {"choices": [{"message": {"content": '{"a": 1}'}}]},
    )
    assert OpenAICompatibleBackend("http://127.0.0.1:1234/v1", "m").generate_json("s", "u") == {"a": 1}


def test_anthropic_json(monkeypatch):
    monkeypatch.setattr(
        _http,
        "post_json",
        lambda *a, **k: {"content": [{"type": "text", "text": '{"ok": true}'}]},
    )
    assert AnthropicBackend().generate_json("s", "u") == {"ok": True}


def test_extract_json_object_tolerant():
    assert _http.extract_json_object('```json\n{"x": 1}\n```') == {"x": 1}
    assert _http.extract_json_object('here you go: {"y": 2} thanks') == {"y": 2}
    with pytest.raises(ValueError):
        _http.extract_json_object("no json here")
