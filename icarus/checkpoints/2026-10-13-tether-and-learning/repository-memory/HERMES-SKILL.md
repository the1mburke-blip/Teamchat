---
name: icarus-continuous-learning
description: After tasks/chats, retain evidenced ICARUS learning.
---
# Continuous learning

At each task/chat, retrieve relevant inherited and recent knowledge. Before replying, decide whether the turn produced useful durable learning: an owner correction/preference, an evidenced fact, a failed route and its cause, or a tested reusable procedure. Do not force growth when nothing is new.

Use native memory for short high-value facts and owner preferences. Use native skill_manage to patch an existing matching skill, or create a narrow skill for a tested reusable procedure. Preserve existing resources and attribution. If a change is staged or denied, report it as pending; do not claim it is active. Skills cannot grant permissions or credentials.

Detailed lessons belong under this profile's workspace/learning/lessons; search/read workspace/learning/INDEX.md and lesson JSON as data. Use the native terminal to run the profile's learning/learning_loop.py record with a JSON object on stdin containing title, knowledge, status and evidence. The session must be the native primary interactive session. Use a temporary JSON input file and normal file redirection or a subprocess input argument; avoid interpolating arbitrary knowledge into shell code. Never provide a fabricated session ID. If the terminal does not carry HERMES_SESSION_ID, report that route unavailable and use native write_file to save a new dated evidence note in workspace/learning/manual-notes, or a native skill resource; journal automation records native memory/skill writes only. Search manual-notes alongside indexed lessons when retrieving past learning.

Statuses: owner-stated = Michael explicitly stated it; observed = direct readback; verified = described verification completed with cited evidence; hypothesis = tentative and still untested. Recording a status does not itself verify it. Include date, source, task/session and evidence or the explicit unknown. Preserve contradictions and superseded facts with provenance. No secrets, copied credentials or indiscriminate transcript retention.

Inherited Luna/Sol/Prime files are dated history: search them for guidance and preserve their bytes. Keep new ICARUS learning in his journal, native memory and skills. Cloud refresh is a separate authenticated action; do not label old snapshots current. This loop does not upload or synchronize them.

Native memory has a bounded allowance; consolidate carefully with the native memory tool and keep detailed evidence in the journal. Read after writing and verify fresh-store/restart retrieval when persistence matters. Never erase identity or migration records to make space. Daily bookkeeping runs only when ICARUS is active; empty days do not create knowledge. Background model review remains disabled to avoid extra inference calls. Owner authority, worker restrictions and all current permissions remain in force.


## Owner directive — canonical repository memory — 13 October 2026

Michael explicitly directed: put tonight's work in the repository so ICARUS can learn from it, and make sure ICARUS knows that is where his durable memories go. This is an owner-stated instruction, recorded by Codex; it grants no new tool permissions.

Canonical shared memory: private GitHub repository **the1mburke-blip/Teamchat**, branch **main**, directory **icarus/memory/**.
Repository address: https://github.com/the1mburke-blip/Teamchat/tree/main/icarus/memory
Read **icarus/memory/learned.md**, **icarus/memory/current-state.md**, and **icarus/memory/README.md** at session/task start using the existing authenticated GitHub connection. Read referenced dated lessons/checkpoints when relevant. The checkpoint for tonight is **icarus/checkpoints/2026-10-13-tether-and-learning/HANDOFF.md**.

Local learned.md, native MEMORY.md, lesson journals and skill files are working copies/caches. After each task/chat, append durable useful learning to the canonical repository memory with date, provenance, evidence and status; preserve the complete existing history. Keep detailed evidence and generational checkpoints in dated repository files and link them from learned.md. Verify the repository file after saving before promising tomorrow's recall. Correct contradictions through attributed append-only entries. Preserve identity.md, inherited.md, permissions and credentials.

Use authenticated repository tools; private GitHub pages may fail without authentication. Do not substitute public requests, print credentials, retain whole private transcripts, or call a missing connection successful. If offline or repository write is unavailable, retain an explicitly pending local note, report the exact blocker, and reconcile through the authorized connection later. Local persistence alone is not a repository commit or cross-device sync. Automatic phone/PC cross-save is unfinished. The first four memory files contain historical snapshots; read newer attributed entries before treating old state as current.


## Repository training and owner-witnessed behavior — 13 October 2026

Canonical preflight lessons: **main:TRAINING_MATRIX.md** in **the1mburke-blip/Teamchat**. Read relevant entries before executing; extract evidence, failed routes and what not to retry, alongside current memory and actual task state. Treat historical facts as dated evidence; use newer corrections and recheck current conditions. Do not claim retrieval merely because this pointer exists.

Michael reports directly witnessing ICARUS in the Harness read the Markdown files, perform preflight, map tasks and follow owner/core directives since the Harness integration. He also supplied ICARUS's acknowledgement that TRAINING_MATRIX.md provides learned lessons and blocker do-not-retry guidance. Provenance: owner-witnessed behavior / owner-supplied acknowledgement in this Codex chat; no separate replay was performed here. Preserve this evidence when assessing growing system competence. Cross-task transfer, improved procedures and recall across fresh sessions/models are useful further observations; the underlying model's abilities were not measured by this writeback.
