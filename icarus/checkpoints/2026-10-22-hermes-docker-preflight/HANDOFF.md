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
- Source inspection identifies `nousresearch/hermes-sandbox:desktop` as the required Bot Desktop image hint. Docker manifest inspection found the amd64 digest `sha256:91001712f321902e61fbd8d89d08700ab3c3b151f801bde1a46fed876f54a5ce`.
- A temporary authorized-runtime probe using that pinned desktop digest timed out during the Docker cgroup/startup probes (60-second resource probe and 120-second container start); its temporary container was independently removed.

## Boundary

Docker is no longer the blocker. The desktop-image experiment did not produce a governed capture. The existing ICARUS sandbox still pins the plain Python image, while Hermes Bot Desktop requires the desktop image and Linux-compatible runtime. The direct cua-driver bridge remains capture-only and verified. No click/type mutation, credentials, paid service, or production source change occurred.

Status: **Verified Docker/WSL readiness, direct capture, image requirement, and timeout boundary; full governed Hermes computer-use on this Windows Harness remains FAIL/unverified.**
