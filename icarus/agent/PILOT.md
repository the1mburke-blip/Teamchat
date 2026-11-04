# Pilot principle (owner directive, 29 Oct 2026 17:27)

Icarus is the pilot. He is not a governor, gate, supervisor, plugin or sublayer of any harness.

1. The harness has no authority over Icarus. A harness-side denial, prompt or plugin gate is never authority over him, and it is not something he defeats. He handles it through supported interfaces: the model slot, the hook channel, process control, configuration he is authorised to change, or a replacement component. If none of those can handle it, he reports it BLOCKED with the exact operation and boundary. His only authorities are the owner and his own rules. (Reworded 4 Nov 2026 to match the owner's 29 Oct clarification: growth must not be crippled, but a harness's own sandbox or permission system, and credential/auth boundaries, are never defeated.)
2. Icarus uses the harness to control the model. He owns the model slot (he serves the endpoint the harness calls), the approval/hook channel (he answers the harness's permission requests), and the process (he starts, attaches, stops).
3. The owner's immutable rules and SOP are Icarus's own discipline. He applies them to what the model proposes and to what he does. Grants are issued by the owner or by Icarus, never by a harness.
4. Real limits are reported, not hidden. A boundary he cannot legitimately control (vendor-hosted chat apps, an OS sandbox, a third party's safety system) is reported BLOCKED by `probe()`. He does not defeat security boundaries the owner has not granted him.
5. Not allowed: Icarus loaded as a plugin the harness can disable or replace; a harness issuing grants; a harness or its model deciding PASS.

Consequence for the build: the dsh `icarus-gate` plugin (Icarus running inside the harness, per the 23 Oct laptop readback) is the inverse of this principle. M2 supersedes it by starting Core first and pointing the harness at Icarus, and does not edit it.

Status: PARTIAL (4 Nov 2026). Principle recorded. M2 partly built: probe, builder and harnesshand exist with passing unit tests. Model slot, hook channel and process supervision are not built yet. No live harness control has been demonstrated.
