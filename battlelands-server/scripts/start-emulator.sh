#!/bin/bash
# Start the Battlelands emulator
export ANDROID_HOME=/home/tom/android-sdk
export PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH

AVD_NAME="${1:-battlelands}"
PORT="${2:-5554}"
RAM="${3:-2048}"

echo "Starting emulator: $AVD_NAME on port $PORT (${RAM}MB RAM)..."
$ANDROID_HOME/emulator/emulator -avd "$AVD_NAME" -port "$PORT" -memory "$RAM" -no-boot-anim -netdelay none -netspeed full -gpu auto &
EMU_PID=$!
echo "Emulator PID: $EMU_PID"
echo "Waiting for boot..."
$ANDROID_HOME/platform-tools/adb -s emulator-$PORT wait-for-device
echo "Device online. Waiting for system boot..."
while [ "$($ANDROID_HOME/platform-tools/adb -s emulator-$PORT shell getprop sys.boot_completed 2>/dev/null)" != "1" ]; do
    sleep 2
done
echo "Emulator ready!"
echo "PID=$EMU_PID" > /tmp/emulator.pid
