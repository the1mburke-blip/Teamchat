# Icarus Android — Blocker 9: Authenticate user and app to the broker

- date: 2026-10-02
- status: RESOLVED_ARCHITECTURALLY
- cost_target: €0

## Blocker
The Icarus broker must know both:
1. which human is making the request
2. that the request is coming from an authentic Icarus Android build

A task/session ID alone is not an authorization boundary.

## Decision
Use Firebase Authentication + Firebase App Check.

### Human identity
Use Android Credential Manager with Sign in with Google, then authenticate to Firebase.
Firebase UID is the canonical mobile user identifier.

Map:
Firebase UID -> Icarus user ID -> Composio user/session namespace -> Drive cross-save namespace.

### App attestation
Use Firebase App Check with Play Integrity on production Android builds.
Every broker request must carry:
- Firebase ID token
- valid App Check token

Broker rejects requests when either token is missing/invalid.

### Debug/development
Use Firebase App Check debug provider only for debug builds and CI/emulator testing.
Never commit or ship the debug token in production.

### Why
Authentication proves who the user is.
App Check reduces abuse by proving requests originate from an authentic app/device context.
Neither replaces the other.

## Broker authorization rule
After token verification:
- derive user identity server-side from Firebase token
- never accept a client-supplied Composio user ID as authoritative
- scope all task/session/cross-save access to that derived UID
- reject cross-user task IDs

## PASS gate
1. Valid signed-in app -> broker accepts.
2. Valid user token but invalid/missing App Check -> rejected.
3. Valid App Check but invalid user token -> rejected.
4. User A cannot access User B task/session IDs.
