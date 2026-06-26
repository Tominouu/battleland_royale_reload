#!/bin/bash
# Collect logcat output filtered for PlayFab/Photon/Unity/Battlelands
export ANDROID_HOME=/home/tom/android-sdk
export PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH

SERIAL="${1:-emulator-5554}"
OUTPUT_DIR="${2:-/home/tom/Téléchargements/battleland_royale_reload/battlelands-server/logs}"
mkdir -p "$OUTPUT_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOGFILE="$OUTPUT_DIR/logcat_$TIMESTAMP.txt"
ERRFILE="$OUTPUT_DIR/errors_$TIMESTAMP.txt"

echo "Collecting logs from $SERIAL to $LOGFILE"
echo "Press Ctrl+C to stop"

# Capture all logs first, then filter in background
$ANDROID_HOME/platform-tools/adb -s "$SERIAL" logcat -v threadtime 2>/dev/null | tee "$LOGFILE" | grep -iE "PlayFab|Photon|Unity|Battlelands|Futureplay|Quantum|Firebase|ConfigLoader|Lobby|Login|Error|Exception|FATAL" > "$ERRFILE"
