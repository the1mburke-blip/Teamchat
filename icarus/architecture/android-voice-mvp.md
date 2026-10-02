# Icarus Android — Blocker 4: Voice-first without a background voice server

- date: 2026-10-02
- status: RESOLVED_FOR_MVP
- cost_target: €0
- requirement: Voice is day-one primary input; text is fallback.

## Blocker
A voice-first Android app can accidentally expand into an always-listening background assistant, which triggers microphone, foreground-service, battery, privacy, and Play-policy complexity.

## Decision
MVP voice interaction is push-to-talk while Icarus is visible.

### Speech input
1. Request RECORD_AUDIO at the user gesture.
2. Prefer Android on-device SpeechRecognizer when available (API 31+).
3. Fall back to the device's normal SpeechRecognizer service when on-device recognition is unavailable.
4. Capture one user utterance per interaction; do not implement continuous always-on recognition.
5. Keep text entry as fallback.

### Speech output
Use Android TextToSpeech for result/status speech.
No remote TTS service is required for MVP.

## Why
Android's SpeechRecognizer supports on-device recognition where available, but the platform explicitly warns that the recognizer is not intended for continuous recognition. Modern Android also restricts background-started microphone foreground services.

## MVP UX
Tap/hold microphone -> speak naturally -> transcript -> Icarus executes -> verified result appears -> Icarus optionally speaks the result.

## Explicitly out of scope for MVP
- hotword/wake-word listening
- continuous background microphone
- always-on voice daemon
- replacing the system voice assistant
- background microphone service launched while the app is hidden

These can be reconsidered only after the core fixer loop is physically proven.

## PASS gate
On target phone:
- microphone permission granted from visible activity
- spoken request reliably transcribes
- text fallback works
- verified result is rendered
- Android TTS speaks the result
- no server is required for speech recognition/TTS itself
