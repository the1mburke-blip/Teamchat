# Hermes Docker prerequisite preflight

Date: 2026-10-22 Europe/London
Provenance: Michael authorized obtaining free Docker Desktop and supplied the Windows virtualization feature command.

## Evidence

- Windows 11 Pro build 26200 was observed.
- Winget found and installed Docker Desktop 4.96.2 at no paid-service cost.
- Docker CLI client 29.9.2 is installed, but the server reported: `Docker Desktop is unable to start`.
- WSL reported that the Windows Subsystem for Linux is not installed.
- `Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform` was attempted and failed because the operation requires elevation.
- A separate elevated-process attempt also exited with code 1; successful feature state could not be independently read without elevation.

## Boundary

No credentials, paid service, or Docker account secret was used. The Hermes governed capture test cannot be rerun until VirtualMachinePlatform/WSL is successfully enabled and Docker Desktop starts.

Status: **Observed Docker client installation; Docker daemon and virtualization prerequisite remain FAIL/not ready pending successful administrator elevation.**
