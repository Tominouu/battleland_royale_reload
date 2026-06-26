#!/bin/bash
# Install Battlelands APK on emulator
export ANDROID_HOME=/home/tom/android-sdk
export PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH

APK_PATH="${1:-/home/tom/Téléchargements/battleland_royale_reload/battlelands-royale-2-9-6.apk}"
SERIAL="${2:-emulator-5554}"

if [ ! -f "$APK_PATH" ]; then
    echo "APK not found: $APK_PATH"
    exit 1
fi

echo "Installing $APK_PATH on $SERIAL..."
$ANDROID_HOME/platform-tools/adb -s "$SERIAL" install -r "$APK_PATH" 2>&1
if [ $? -eq 0 ]; then
    echo "Installation successful!"
else
    echo "Installation failed"
    exit 1
fi
