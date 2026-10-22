# Hermes Docker prerequisite preflight

Date: 2026-10-22 Europe/London
Provenance: Michael authorized obtaining free Docker Desktop and supplied the Windows virtualization feature command.

## Evidence

- Windows 11 Pro build 26200 was observed; firmware virtualization was enabled on an 11th Gen Intel processor.
- Winget installed Docker Desktop 4.96.2 at no paid-service cost.
- `Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -All -NoRestart` completed in an elevated PowerShell with exit code 0 and reported `Online: True` and `RestartNeeded: True`.
- After the owner-approved reboot, WSL reported default version 2 with no virtualization error.
- Docker Desktop started successfully. `docker version` returned client/server 29.9.2 with a Linux engine; `docker info` reported 0 containers and the overlayfs engine.
- A fresh direct Hermes bridge capture returned a 1920x1080 PNG, 885105 bytes, SHA-256 `afa761573be8de8b709b4852bd45c21046ab428b0a29e8537431633392fcdc20`; independent image readback verified it.
- The high-level Hermes capture was initially blocked by source/runtime issues. Source inspection identified `nousresearch/hermes-sandbox:desktop` as the required Bot Desktop image hint; Docker manifest inspection found amd64 digest `sha256:91001712f321902e61fbd8d89d08700ab3c3b151f801bde1a46fed876f54a5ce`.
- Minimal source repair: `agent/icarus_sandbox.py` now pins the desktop image by digest, and `tools/bot_desktop/runtime.py` uses a Windows `msvcrt` lock path for host-side Bot Desktop state instead of POSIX-only `fcntl`. Both files compiled successfully.
- A fresh explicit `IcarusRuntime` turn using the permanent image pin returned a multimodal governed Hermes `capture`: mode `som`, 88x44 pixels, app `Xfce4-panel`, one reported interactable element, cache image `computer_use_62f9b86d0c934d3698876a50b73a13c1.png`. Independent image readback verified 88x44 PNG, 1042 bytes, SHA-256 `b23c20d6c8df57c19fea76d6515073d6aa389bb69399291b9aa375a031f9e9c7`.
- After the repair and reboot, the existing Harness host was observed running and the desktop profile dependency graph still contained linked `@deepseek-ai/dsh-hermes-computer-use`.
- The capture-only live profile bridge returned a fresh 1920x1080 PNG at `C:\Users\the1m\OneDrive\Desktop\hermes-captures\hermes-capture-09f54139b0b095de.png`, 512365 bytes, SHA-256 `09f54139b0b095de345e256fd7e59953d7248b2cd8ce2286563f2fe0529050eb`; independent image readback showed the live DeepSeek Harness UI.

## Boundary

The governed capture is verified inside an explicit local ICARUS runtime and governed Docker sandbox, and the live profile capture-only bridge is verified. This is not proof of a model-issued tool call through the live DSH UI because the current API session cannot invoke the newly registered plugin namespace directly. No click/type mutation, credentials, paid service, or production source change occurred.

Status: **Verified Docker/WSL readiness, source-repaired governed Hermes capture, live profile linkage, and fresh direct capture; model-issued live Harness `computer_use` invocation remains unverified.**
