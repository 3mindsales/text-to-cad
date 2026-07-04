# ADR-0004 — Ollama local default; Ollama Cloud as a gated non-local Boost

- Status: Accepted
- Date: 2026-07-04

## Context

The typical deployment machine is a modest, often GPU-less office/shop PC. We need a reliable
local default and an escape hatch to a strong model for the occasional Freeform/complex request,
without breaking the air-gap promise for users who require it.

## Decision

Default runtime is a **bundled local Ollama** serving an offline GGUF from `127.0.0.1:11434`
(with an in-process `llama-cpp-python` fallback). A model is **local only** if it is an offline
GGUF on localhost. **Ollama Cloud** is offered as an opt-in **"Boost"** through the *same* client:
any tag ending in `-cloud`, or any non-local host, is classified **non-local** — `is_local()`
returns `False`, which triggers the external-provider opt-in gate and the persistent
"ONLINE LLM ACTIVE" badge (I4). Hybrid routing is allowed: Template calls stay local, Freeform
may Boost. In an `AIRGAP_STRICT` build, cloud is **impossible**, not merely unselected (SPEC 9.5).

## Consequences

- Weak machines get a working default (Template) and an optional strong path (cloud Freeform).
- "It's still Ollama" never launders a cloud call into looking air-gapped — the `is_local()`
  truth-table (with `-cloud`/remote-host cases) is a permanent regression guard.
- External adapters read keys from OS keyring/env, never plaintext config; keys are never logged.
