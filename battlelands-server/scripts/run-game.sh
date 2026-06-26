#!/bin/bash
# Launch Battlelands on emulator
export ANDROID_HOME=/home/tom/android-sdk
export PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH

SERIAL="${1:-emulator-5554}"

echo "Launching Battlelands Royale on $SERIAL..."
$ANDROID_HOME/platform-tools/adb -s "$SERIAL" shell am start -n "com.futureplay.battleground/com.futureplay.battleground.unityactivity" -a android.intent.action.MAIN -c android.intent.category.LAUNCHER 2>&1
echo "Game launched!"
