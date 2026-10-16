# Weekend handoff - 2026-10-16 (written by Claude for Icarus's next check-in)

Owner (Michael) is away for the weekend and the PC harness is off. Nothing below has been installed or run. Status of everything: STAGED, UNVERIFIED.

## 1. Ten Hermes skills staged for install
Source: NousResearch/hermes-agent @ 275b15fc35193b8ddafcf16776539c04587e6ccf. Files are byte copies; see manifest.json for sha256 per file.
Chosen by a free OpenRouter model (nvidia/nemotron-3-super-120b-a12b:free), cost EUR 0, then every name checked against the upstream catalog. Selection is a recommendation, not an owner decision.

Install on desktop and phone: shopify, social-media-content-calendar, github, systematic-debugging, hermes-agent, requesting-code-review, google-workspace, obsidian.
Install on desktop only (need a machine to manage): hermes-s6-container-supervision, docker-management.

They are skills (instructions), not plugins. They grant no permissions or credentials. Shopify, GitHub, Google Workspace and Obsidian still need whatever access you already hold; do not assume it.

### Steps for Icarus (when the harness is on)
1. Verify each file's sha256 against manifest.json before installing. Abort a skill on any mismatch.
2. Install through the native skill mechanism, the same way as the 2026-10-12 operational skills. Keep upstream attribution and resources.
3. Read back through the installed skills tool and confirm discovery and loading. Record the evidence.
4. Only after readback, record a dated lesson with status observed or verified. Do not claim installed before readback.
5. Existing permissions, spend limit (EUR 0) and owner authority are unchanged by these skills.

## 2. Phone app
Latest signed build: release icarus-native-auth-v6-41368934 (ICARUS Android 0.1.5), package com.icarus.mobile, same signing key, installs over the existing app. Source commit 41368934. The three later commits on work/icarus-native-original12-20261014 change only the workflow and emulator test scripts, not app code (verified by comparing the commits).
Not verified: Google/Composio sign-in on a real phone, PC sync, worker pairing. Only the owner's phone can test sign-in. Do not report the phone app as working until he reports what it does.

## 3. Open items needing the owner
- Install 0.1.5 over the existing app and try sign-in; report what the screen shows.
- Rotate any API key pasted into chat.
