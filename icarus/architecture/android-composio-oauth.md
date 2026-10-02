# Icarus Android — Blocker 5: Composio/provider OAuth return to the app

- date: 2026-10-02
- status: RESOLVED_ARCHITECTURALLY
- cost_target: €0

## Blocker
Mobile Icarus must connect Gmail, Drive and other providers without embedding provider secrets, using an insecure WebView, or leaving the user stranded in a browser after OAuth.

## Decision
Use Composio Connect Links + Android Custom Tabs + a verified HTTPS Android App Link on the Icarus broker domain.

## Flow
1. Android asks the Icarus broker to authorize a toolkit for the stable Icarus user ID.
2. Broker creates a Composio Connect Link/session authorization request.
3. Android opens the returned HTTPS URL in a Custom Tab.
4. User completes provider consent on the provider/Composio hosted flow.
5. Composio returns to an HTTPS callback owned by the Icarus broker domain.
6. Broker completes/validates the auth flow and redirects to the verified Icarus App Link.
7. Android resumes and polls/reads connection state until ACTIVE.
8. Raw provider OAuth credentials never enter the APK.

## Android link security
Use Android App Links with android:autoVerify=true.
Host /.well-known/assetlinks.json on the Icarus broker domain with the app package and signing-certificate fingerprint.

For development, explicitly support the debug signing fingerprint separately from the release fingerprint.

## Browser rule
Use Custom Tabs for provider login/consent.
Do not embed third-party OAuth in WebView.

## Consumer-hardening
Before multi-user release, enable Composio callback identity verification so a copied Connect Link cannot attach the wrong upstream account to another Icarus user.

## PASS gate
From a fresh install:
- request connection in Icarus
- consent in Custom Tab
- return automatically to Icarus through verified App Link
- connection reads ACTIVE for the correct stable user ID
- execute one harmless read through that connection
- no raw OAuth token is present in app storage/logs
