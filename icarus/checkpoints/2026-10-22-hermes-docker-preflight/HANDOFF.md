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
- The high-level Hermes capture was rerun after Docker readiness. In an explicit local `IcarusRuntime` turn, it returned `computer_use backend unavailable: No module named 'fcntl'` and logged `ICARUS container target requires admitted execution`; the ordinary standalone path still reports missing ICARUS runtime authority.
- Hermes Bot Desktop source gates the gateway host to Linux (`is_supported_host(): sys.platform.startswith("linux")`).

## Boundary

Docker is no longer the blocker. The remaining failure is the Windows/source-governed Bot Desktop and ICARUS admission integration. The direct cua-driver bridge remains capture-only and verified. No click/type mutation, credentials, or paid service occurred.

Status: **Verified Docker/WSL readiness and fresh direct capture; full governed Hermes computer-use on this Windows Harness remains FAIL/unverified.**
