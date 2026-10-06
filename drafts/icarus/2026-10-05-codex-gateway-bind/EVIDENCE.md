# Icarus clean recovery candidate — BUILD REQUESTED

Date: 2026-10-06
Branch: fix/icarus-clean-install-20261006
Cost: €0

Changes included before build:
- current package id: com.aistudio.icarus.appsscript
- signed-v1 envelope using ICARUS_QUEUE_V1
- no plaintext token in signed submit/status payloads
- REASONING and READY_FOR_EXECUTION treated as progressing states
- WAITING/PENDING_AUTH and unknown terminal states release the local composer
- 60-second local wait timeout returns a releasable VERIFYING state
- New Task can cancel stale local UI state
- force-stop/relaunch does not restore a persisted current-task pointer
- secure token remains AndroidKeyStore AES-GCM backed

Boundary:
- no credential embedded in source/APK
- no live backend mutation
- fresh pairing is still required because the prior app was uninstalled
- server-side Google Sheets 50k persistence defect is not claimed fixed by this APK

PASS gate for this artifact:
compile + static signed-v1 gates + emulator launch + APK hash.
Physical Redmi/backend execution remains separate.
