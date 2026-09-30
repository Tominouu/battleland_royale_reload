#!/usr/bin/env bash
# Build the minimal libmain.so (arm64-v8a) with the Android NDK.
#   ANDROID_NDK_HOME=~/Android/Sdk/ndk/27.2.12479018 ./build.sh 203.0.113.10 4530
#   BLR_DRY_RUN=1 ./build.sh ...   -> log AppID/version/region only, no redirect
set -euo pipefail

HOST="${1:?usage: build.sh <photon_ip> [port]}"
PORT="${2:-4530}"
NDK="${ANDROID_NDK_HOME:?set ANDROID_NDK_HOME to an Android NDK (r21+)}"
CC="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android21-clang"
OUT="$(dirname "$0")/out"
mkdir -p "$OUT"

"$CC" -shared -fPIC -O2 -Wall -Wextra -ffreestanding -fvisibility=hidden \
    -DBLR_PHOTON_HOST="\"$HOST\"" -DBLR_PHOTON_PORT="$PORT" \
    -DBLR_DRY_RUN="${BLR_DRY_RUN:-0}" -DBLR_REDIRECT_ALL_REGIONS="${BLR_REDIRECT_ALL_REGIONS:-1}" \
    -Wl,-soname,libmain.so -Wl,--build-id \
    -o "$OUT/libmain.so" "$(dirname "$0")/blr_redirect.c" -ldl -llog

echo "built $OUT/libmain.so -> Photon $HOST:$PORT"
