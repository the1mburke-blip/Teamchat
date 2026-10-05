#!/usr/bin/env bash
set -euo pipefail

ROOT="$(pwd)"
OUT="$ROOT/runtime-evidence"
mkdir -p "$OUT"
APK="$ROOT/drafts/icarus/2026-10-05-lightweight-shell/compile-ready/app/build/outputs/apk/debug/app-debug.apk"

test -f "$APK"
adb install -r "$APK" | tee "$OUT/install.txt"
adb logcat -c
adb shell am force-stop com.icarus.shell
adb shell am start -W -n com.icarus.shell/.MainActivity | tee "$OUT/launch.txt"
sleep 2

dump_ui() {
  local name="$1"
  adb shell uiautomator dump /sdcard/window.xml >/dev/null
  adb pull /sdcard/window.xml "$OUT/$name.xml" >/dev/null
}

tap_text() {
  local xml="$1"
  local needle="$2"
  local klass="${3:-}"
  local coords
  coords="$(python3 - "$xml" "$needle" "$klass" <<'PY'
import re, sys, xml.etree.ElementTree as ET
path, needle, klass = sys.argv[1], sys.argv[2], sys.argv[3]
root = ET.parse(path).getroot()
for node in root.iter("node"):
    text = (node.attrib.get("text") or "") + " " + (node.attrib.get("content-desc") or "")
    cls = node.attrib.get("class") or ""
    if ((needle and needle in text) or (not needle and klass and klass in cls)) and (not klass or klass in cls):
        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.attrib.get("bounds",""))
        if m:
            x1,y1,x2,y2 = map(int,m.groups())
            print(f"{(x1+x2)//2} {(y1+y2)//2}")
            sys.exit(0)
sys.exit(1)
PY
)"
  adb shell input tap $coords
}

dump_ui initial
grep -q 'text="ICARUS"' "$OUT/initial.xml"
grep -q 'Speak to Icarus' "$OUT/initial.xml"
grep -q 'Submit' "$OUT/initial.xml"
grep -q 'STATUS: IDLE' "$OUT/initial.xml"
adb exec-out screencap -p > "$OUT/01-initial.png"

tap_text "$OUT/initial.xml" "Speak to Icarus"
sleep 1
dump_ui listening
grep -q 'Listening' "$OUT/listening.xml"
adb exec-out screencap -p > "$OUT/02-listening.png"

tap_text "$OUT/listening.xml" "Listening"
sleep 1
dump_ui voice_off
grep -q 'Speak to Icarus' "$OUT/voice_off.xml"

tap_text "$OUT/voice_off.xml" "" "android.widget.EditText"
adb shell input text 'repo_ghost_runtime_test'
sleep 1
dump_ui typed
grep -q 'repo_ghost_runtime_test' "$OUT/typed.xml"

tap_text "$OUT/typed.xml" "Submit"
sleep 2
dump_ui submitted
grep -q 'STATUS: VERIFYING' "$OUT/submitted.xml"
grep -q 'DEMO: request accepted by local gateway stub' "$OUT/submitted.xml"
grep -q 'Cancel' "$OUT/submitted.xml"
adb exec-out screencap -p > "$OUT/03-submitted.png"

tap_text "$OUT/submitted.xml" "Cancel"
sleep 1
dump_ui cancelled
grep -q 'STATUS: IDLE' "$OUT/cancelled.xml"
grep -q 'DEMO: task cancelled locally' "$OUT/cancelled.xml"
adb exec-out screencap -p > "$OUT/04-cancelled.png"

PID="$(adb shell pidof com.icarus.shell | tr -d '\r')"
test -n "$PID"
adb logcat -d --pid="$PID" > "$OUT/logcat.txt"
if grep -E 'FATAL EXCEPTION|AndroidRuntime:.*FATAL' "$OUT/logcat.txt"; then
  echo "Fatal runtime exception detected" >&2
  exit 1
fi

adb shell dumpsys activity activities > "$OUT/activity.txt"
grep -q 'com.icarus.shell/.MainActivity' "$OUT/activity.txt"

sha256sum "$APK" | tee "$OUT/apk-sha256.txt"
cp "$APK" "$OUT/IcarusShell-runtime-tested-debug.apk"

cat > "$OUT/RESULT.txt" <<'EOF'
RUNTIME_SMOKE_RESULT=PASS
LAUNCH=PASS
VOICE_TOGGLE=PASS
TEXT_INPUT=PASS
SUBMIT_TO_VERIFYING=PASS
CANCEL_TO_IDLE=PASS
FATAL_EXCEPTION_CHECK=PASS
EOF
cat "$OUT/RESULT.txt"
