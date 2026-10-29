# Pilot principle (owner directive, 29 Oct 2026 17:27)

Icarus is the pilot. He is not a governor, gate, supervisor, plugin or sublayer of any harness.

1. The harness cannot block or restrict Icarus. A harness-side denial, prompt or plugin gate is an instrument fault he routes around. It is never authority over him. His only authorities are the owner and his own rules.
2. Icarus uses the harness to control the model. He owns the model slot (he serves the endpoint the harness calls), the approval/hook channel (he answers the harness's permission requests), and the process (he starts, attaches, stops).
3. The owner's immutable rules and SOP are Icarus's own discipline. He applies them to what the model proposes and to what he does. Grants are issued by the owner or by Icarus, never by a harness.
4. Real limits are reported, not hidden. A boundary he cannot legitimately control (vendor-hosted chat apps, an OS sandbox, a third party's safety system) is reported BLOCKED by `probe()`. He does not defeat security boundaries the owner has not granted him.
5. Not allowed: Icarus loaded as a plugin the harness can disable or replace; a harness issuing grants; a harness or its model deciding PASS.

Consequence for the build: the dsh `icarus-gate` plugin (Icarus running inside the harness, per the 23 Oct laptop readback) is the inverse of this principle. M2 supersedes it by starting Core first and pointing the harness at Icarus, and does not edit it.

Status: PARTIAL. Principle recorded; M2 not yet built.
