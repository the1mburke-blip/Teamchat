# Voice Skill Default Settings

## Default Voice Configuration
This file defines the default voice settings for the ICARUS voice skill.

## Settings
- **Voice Engine**: Windows Speech API (`System.Speech`)
- **Output**: System default audio device
- **Default Speech Rate**: 170 words per minute
- **Default Volume**: 80%
- **Voice Type**: Neural (platform default)

## Usage
- Set `voice: true` or `voice_enabled: true` in task description to activate voice output
- Voice output is automatically applied to all responses unless explicitly disabled
- Use `voice: false` to request text-only responses

## Technical Details
- **Synthesis Method**: `[System.Speech.Synthesis.SpeechSynthesizer]::new()`
- **Audio Output**: Windows default audio endpoint
- **Silence Handling**: Default system volume control

## Status
This file provides the foundational voice skill configuration for ICARUS.