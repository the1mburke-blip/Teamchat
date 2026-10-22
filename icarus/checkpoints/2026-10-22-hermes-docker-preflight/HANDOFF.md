# Hermes Docker prerequisite preflight

Date: 2026-10-22 Europe/London
Provenance: Michael authorized obtaining free Docker Desktop and supplied the Windows virtualization feature command.

## Evidence

- Windows 11 Pro build 26200 was observed; firmware virtualization was enabled on an 11th Gen Intel processor.
- Winget found and installed Docker Desktop 4.96.2 at no paid-service cost.
- Docker CLI client 29.9.2 is installed, but before reboot the server reported: `Docker Desktop is unable to start`.
- WSL reported that WSL2 could not start because virtualization and Virtual Machine Platform were not enabled.
- A normal feature-enable attempt failed for lack of elevation. A second explicit elevated PowerShell script then completed with exit code 0 and reported `Online: True` and `RestartNeeded: True` for `Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -All -NoRestart`.

## Boundary

Windows restart is required before Docker/WSL readiness can be retested. No automatic reboot was performed. No credentials, paid service, or Docker account secret was used.

Status: **Verified VirtualMachinePlatform enablement pending reboot; Docker daemon remains unverified until restart.**
