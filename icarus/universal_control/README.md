# ICARUS-owned harness worker boundary — isolated candidate

Owner: Michael. Executor: ChatGPT/Sol. 2026-10-10. €0 monetary authorization.

**Purpose:** ICARUS is the stable controlling agent; a harness is a replaceable, untrusted worker. The controller retains its task ID, canonical identity hash, authorization and readback receipt when the worker is replaced.

**Code:** `controller.py` provides an ICARUS-owned task store, protected-note tool broker, deterministic target readback, worker-result adjudication and `DockerHarness` (mandatory isolated Docker execution). `worker_fixture.py` represents two disposable interchangeable harness adapters. The worker speaks `icarus.worker.v1` and cannot directly invoke the host broker.

**OS boundary:** Docker worker launched by ICARUS with an exact local image SHA256, `--network=none`, no bind mounts, no host environment secrets, read-only root, nonroot UID, dropped capabilities, `no-new-privileges`, memory/process/CPU limits. If Docker is missing, the worker does not launch. There is deliberately no unsafe local process fallback.

**Proof:** `python -m unittest discover -s icarus/universal_control -p test_controller.py -v`. GitHub Actions also checks live disposable container isolation, authorized broker effect, replacement A→B, preservation of task and independently reread note contents, and refusal of fake PASS without a valid effect.

**Boundaries:** This is **not** the owner's live installation. It is not an installed DSH or Hermes integration. Their adapters, approved tool inventory, production credential broker, Windows sandbox selection and physical-device acceptance are still unimplemented. A model/provider can always fail; ICARUS must still govern host effects. Container confinement is enforced by the Docker/OS security boundary, not by prompts or ordinary in-process hooks.

Reuse sources: Teamchat PR #91's native permit and effect readback pattern, PR #63's route/replay/evidence contract and TRAINING_MATRIX HV-EXP-082/084. No private memory payload or credentials are copied into a worker image. No production writes, merge, or deployment are authorized.
