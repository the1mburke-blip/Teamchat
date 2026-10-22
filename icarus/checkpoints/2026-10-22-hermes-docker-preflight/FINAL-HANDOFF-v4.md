# Hermes capability-construction lesson v4

Date: 2026-10-22 Europe/London
Provenance: Michael's reflection after the Hermes remediation, supported by verified task evidence.

## Durable lesson

A missing capability can be built incrementally by composing existing verified primitives: install the real runtime dependencies; verify the backend contract; provision the required governed environment; make the narrowest platform repair; register a constrained interface; invoke it harmlessly; and independently read back the final artifact. This can produce a usable capability even when the broader interactive capability is not yet available.

## Evidence

This procedure produced a working Hermes/cua-driver capture bridge, a governed Docker sandbox capture, a live-profile `computer_use` registration limited to `action=capture`, mutation rejection for `click` and extra arguments, and independently verified screenshots. Docker/WSL, source compilation, handler output, image dimensions and SHA-256 readbacks are recorded in the preceding Hermes handoffs.

Boundary: This certifies the capture-only capability, not click/type control or a model-issued live-host call. The native `icarus-continuous-learning` skill procedure was not changed; this is a task-specific learned pattern.

Status: **Verified reusable construction pattern; broader interactive computer-use capability remains unverified.**
