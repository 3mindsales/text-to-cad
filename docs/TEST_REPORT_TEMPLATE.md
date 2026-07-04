# TextToCAD — Clean-VM Test Report (signable)

> Fill one copy per clean-VM run. Attach screenshots where indicated.

- **Build version:** `TextToCAD 0.1.0`
- **Bundle SHA256:** `__________________________`
- **Tester:** `____________`   **Date:** `____________`
- **Signature:** `____________`

## VM specification

| Field | Value |
| --- | --- |
| OS | Windows 10/11 (build ________) |
| Python installed on VM | **none** (bundle is self-contained) |
| CPU / RAM | ____________ |
| GPU / VRAM | ____________ (or "none") |
| Network | **disconnected** (air-gapped) — confirm |
| Model pack installed | 3b / 7b / 14b (circle) |

## Headline acceptance (AC1)

Prompt: **"L-bracket 150 x 80 x 6 mm, four M8 holes, 8 mm inner fillet"**

| Check | Result | Evidence |
| --- | --- | --- |
| Valid STEP produced | PASS / FAIL | screenshot + file |
| Model rendered in viewer | PASS / FAIL | screenshot |
| Cut-list CSV produced | PASS / FAIL | file |
| **Zero network activity** | PASS / FAIL | packet capture / firewall log |
| Byte-identical STEP on re-export (AC3) | PASS / FAIL | hashes |

## Error-scenario matrix (SPEC 12)

| # | Scenario | Expected | Result | Notes |
| --- | --- | --- | --- | --- |
| S1 | Ollama down / model missing | model-pack guidance; UI stays usable; generation blocked | | |
| S2 | LLM returns invalid JSON/schema | self-repair up to 3; then manual-edit offer | | auto-tested |
| S3 | Freeform fails AST / sandbox timeout | rejected + logged; never executed | | auto-tested |
| S4 | Geometry invalid (isValid False / zero vol) | self-repair; last valid kept; invalid not exported | | auto-tested |
| S5 | Values out of envelope (e.g. 50 m plate) | rejected at schema with clear message; no build | | auto-tested |
| S6 | Output folder not writable | error dialog; ask for another folder | | auto-tested |
| S7 | OOM on huge freeform | envelope+tolerance cap; abort build; app alive | | |
| S8 | Close app mid-generation | confirm; terminate worker + sandbox; clean temp | | |
| S9 | GPU/VTK init failure | CPU software fallback; warn; no crash | | auto-tested (fallback) |

## Constrained-machine pass

| Check | Result | Notes |
| --- | --- | --- |
| 3b tier: Freeform forced OFF; Template works | | |
| Ollama Cloud "Boost" path works | | requires network + opt-in |
| "ONLINE LLM ACTIVE" badge shown for cloud/external | | screenshot |
| Boost gated behind the external-provider opt-in | | |
| AIRGAP_STRICT build: cloud impossible | | |

## Licensing

| Check | Result |
| --- | --- |
| Valid license unlocks | |
| Wrong-machine / expired / tampered license fails | |
| Clock rollback locks ("System clock tampered") | |

## Sign-off

All headline and matrix items reviewed. Exceptions noted above.

Tester signature: `______________________`
