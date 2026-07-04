# ADR-0003 — Template mode is the default; Freeform is gated and sandboxed

- Status: Accepted
- Date: 2026-07-04

## Context

Two generation modes are possible: constrained JSON-schema fill (Template) and free CadQuery
code generation (Freeform). Template is highly reliable even on small (3B) local models because
the model only fills validated parameters; Freeform is powerful but risky — both for correctness
and for security (arbitrary code).

## Decision

**Template mode is the default** and is expected to cover the great majority of requests. On the
constrained 3b tier, Freeform is **forced off**. **Freeform is a gated advanced toggle**: LLM-authored
code is treated as untrusted and is AST-whitelisted, then executed in an isolated subprocess with a
wall-clock timeout, a memory cap, no network, and no filesystem writes beyond one result temp file (I6).
Any validation/sandbox failure routes into the self-repair loop (I5).

## Consequences

- Reliable, manufacturable output by default, even on weak hardware.
- The security surface of code execution is contained to one audited, tested boundary
  (the sandbox has a dedicated malicious-snippet test suite).
- Freeform users accept a slower, gated path; complex Freeform may route to a cloud Boost (ADR-0004).
