#!/usr/bin/env bash
# Build libmain.so without the NDK: system clang (aarch64 target) + an LLD (e.g. rustup's rust-lld).
# Link-time stubs for libc/libdl/liblog only provide DT_NEEDED + symbol names; the real
# bionic libraries are used on the device.
#   LLD=~/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/bin/rust-lld \
#   BLR_DRY_RUN=1 ./build-local.sh 127.0.0.1 4530
set -euo pipefail

HOST="${1:?usage: build-local.sh <photon_ip> [port]}"
PORT="${2:-4530}"
LLD="${LLD:?set LLD to an ld.lld / rust-lld binary}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/out"
STUBS="$OUT/stubs"
TARGET=aarch64-linux-android21
CFLAGS=(--target=$TARGET -fPIC -O2 -Wall -Wextra -Werror -ffreestanding -fvisibility=hidden)
mkdir -p "$STUBS"

stub() {   # stub <soname> <symbol>...
    local so="$1"; shift
    printf 'void %s(void) {}\n' "$@" > "$STUBS/${so%.so}.c"
    clang "${CFLAGS[@]}" -fvisibility=default -c "$STUBS/${so%.so}.c" -o "$STUBS/${so%.so}.o"
    "$LLD" -flavor gnu -shared -soname "$so" -o "$STUBS/$so" "$STUBS/${so%.so}.o"
}
stub libc.so mmap mprotect sysconf pthread_create pthread_detach usleep memcpy
stub libdl.so dlopen dlsym dlerror
stub liblog.so __android_log_print

clang "${CFLAGS[@]}" \
    -DBLR_PHOTON_HOST="\"$HOST\"" -DBLR_PHOTON_PORT="$PORT" \
    -DBLR_DRY_RUN="${BLR_DRY_RUN:-0}" -DBLR_REDIRECT_ALL_REGIONS="${BLR_REDIRECT_ALL_REGIONS:-1}" \
    -c "$HERE/blr_redirect.c" -o "$OUT/blr_redirect.o"

"$LLD" -flavor gnu -shared -soname libmain.so --build-id -z now -z relro -z noexecstack \
    --hash-style=both --no-undefined -o "$OUT/libmain.so" "$OUT/blr_redirect.o" \
    -L"$STUBS" -llog -ldl -lc

echo "built $OUT/libmain.so -> Photon $HOST:$PORT (dry run ${BLR_DRY_RUN:-0})"
