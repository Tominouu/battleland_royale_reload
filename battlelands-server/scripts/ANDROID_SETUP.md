# Setup Android SDK + AVD

Exécuter dans l'ordre :

```bash
export ANDROID_HOME=/home/tom/android-sdk
export PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$PATH
$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager "platform-tools" "emulator" "platforms;android-30" "system-images;android-30;google_apis;x86_64"
```

```bash
export ANDROID_HOME=/home/tom/android-sdk
export PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$PATH
echo "no" | $ANDROID_HOME/cmdline-tools/latest/bin/avdmanager create avd -n battlelands -k "system-images;android-30;google_apis;x86_64" -d pixel_6 -f
```

```bash
export ANDROID_HOME=/home/tom/android-sdk
echo "AVDs disponibles :"
$ANDROID_HOME/emulator/emulator -list-avds
echo "adb version :"
$ANDROID_HOME/platform-tools/adb version
```

Ajouter à `~/.bashrc` :

```bash
export ANDROID_HOME=/home/tom/android-sdk
export PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH
```
