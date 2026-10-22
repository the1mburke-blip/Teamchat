# Hermes Docker and live bridge final handoff v2

Date: 2026-10-22 Europe/London
Provenance: Michael authorized free Docker remediation and harmless Hermes capture verification.

## Verified evidence

- Docker Desktop 4.96.2, WSL 2, and Docker client/server 29.9.2 with Linux overlayfs were verified after the owner-approved reboot.
- The pinned amd64 image `nousresearch/hermes-sandbox:desktop@sha256:91001712f321902e61fbd8d89d08700ab3c3b151f801bde1a46fed876f54a5ce` was pulled successfully and its desktop binaries were verified.
- `agent/icarus_sandbox.py` permanently pins that desktop image; `tools/bot_desktop/runtime.py` uses a Windows `msvcrt` host-state lock instead of POSIX-only `fcntl`. Both files compiled.
- An explicit `IcarusRuntime` turn returned a multimodal governed Hermes capture: mode `som`, 88x44 pixels, `Xfce4-panel`, one interactable element; independent readback verified image SHA-256 `b23c20d6c8df57c19fea76d6515073d6aa389bb69399291b9aa375a031f9e9c7`.
- The live DSH profile dependency graph contains linked `@deepseek-ai/dsh-hermes-computer-use`. Its plugin schema was inspected: tool `computer_use`, required `action` with constant `capture`, and `additionalProperties: false`.
- A controlled registration context invoked the registered handler with `{action:"capture"}`. It returned `ok: true`, backend `hermes-cua-driver`, and a fresh 1920x1080 PNG at `C:\Users\the1m\OneDrive\Desktop\hermes-captures\hermes-capture-1fa79a15081c9cbb.png`, 619749 bytes, SHA-256 `1fa79a15081c9cbb4af4b918f9ab88fcf8c08c68b32009564fe5c5f8761c0f5e`; independent image readback verified it.

## Boundary

The governed sandbox capture and the capture-only plugin registration/handler are verified. The controlled registration context is not the already-running Harness host’s model execution loop, so a model-issued call through the live plugin namespace remains unverified. No click/type mutation, credentials, paid service, or production source change occurred.

Status: **Verified Docker/WSL readiness, governed Hermes capture, live profile schema, registered handler invocation, and independent screenshot readback; live-host model-issued plugin invocation remains unverified.**
