# Hermes Docker and governed capture final handoff

Date: 2026-10-22 Europe/London
Provenance: Michael authorized free Docker remediation and harmless Hermes capture verification.

## Verified evidence

- Windows 11 Pro build 26200 and firmware virtualization were observed.
- Docker Desktop 4.96.2 was installed via winget at no paid-service cost.
- VirtualMachinePlatform was enabled in elevated PowerShell, the owner-approved reboot completed, WSL reported default version 2, and Docker Desktop started.
- Docker client/server 29.9.2 and the Linux overlayfs engine were verified by `docker version` and `docker info`.
- The pinned amd64 image `nousresearch/hermes-sandbox:desktop@sha256:91001712f321902e61fbd8d89d08700ab3c3b151f801bde1a46fed876f54a5ce` was pulled successfully and its required desktop binaries were verified.
- Minimal source repair: `agent/icarus_sandbox.py` pins that desktop image; `tools/bot_desktop/runtime.py` uses a Windows `msvcrt` host-state lock instead of POSIX-only `fcntl`. Both files compiled.
- An explicit `IcarusRuntime` turn then returned a multimodal governed Hermes capture: mode `som`, 88x44 pixels, app `Xfce4-panel`, one interactable element, image `computer_use_62f9b86d0c934d3698876a50b73a13c1.png`; independent readback verified 1042 bytes and SHA-256 `b23c20d6c8df57c19fea76d6515073d6aa389bb69399291b9aa375a031f9e9c7`.
- The live DSH desktop profile still contained linked `@deepseek-ai/dsh-hermes-computer-use`; its capture-only bridge returned a fresh 1920x1080 screenshot of the live DeepSeek Harness UI at `C:\Users\the1m\OneDrive\Desktop\hermes-captures\hermes-capture-09f54139b0b095de.png`, 512365 bytes, SHA-256 `09f54139b0b095de345e256fd7e59953d7248b2cd8ce2286563f2fe0529050eb`; independent image readback verified it.

## Boundary

The source-level governed capture and live profile capture-only bridge are verified. A model-issued call through the live DSH plugin namespace was not directly invoked by this API session. No click/type mutation, credentials, paid service, or production source change occurred.

Status: **Verified Docker/WSL readiness, governed Hermes sandbox capture after source repair, live profile linkage, and fresh direct Harness capture; model-issued live-plugin invocation remains unverified.**
