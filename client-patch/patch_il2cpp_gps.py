#!/usr/bin/env python3
"""Experimental: make FuturePlay.GooglePlayServicesChecker.UpToDate() return true (2.9.6 arm64 only).

GameLoader.Start only starts LoadingRoutine if UpToDate() (JNI -> GPSChecker.checkPlayServices)
returns true; without Google Play Services the game stays at "1".

  RVA 0x103CFF4  static bool UpToDate()   (Il2CppDumper, original 2.9.6 libil2cpp.so)
  original : str x21,[sp,#-0x30]! ; stp x20,x19,[sp,#0x10]   f5 0f 1d f8  f4 4f 01 a9
  patched  : mov w0,#1            ; ret                      20 00 80 52  c0 03 5f d6

Only these 8 bytes change; the rest of the function is left in place (revert = restore them).
"""
import hashlib
import sys

ORIGINAL_SHA256 = '6b84bb234433c3b3ca19426beb2918eb990d70a6973a035c3e8e9329105bd44f'
RVA = 0x103CFF4
ORIGINAL = bytes.fromhex('f50f1df8f44f01a9')
PATCHED = bytes.fromhex('20008052c0035fd6')


def main():
    if len(sys.argv) != 3:
        sys.exit('usage: patch_il2cpp_gps.py <original libil2cpp.so> <output>')
    data = bytearray(open(sys.argv[1], 'rb').read())
    sha = hashlib.sha256(data).hexdigest()
    if sha != ORIGINAL_SHA256:
        sys.exit(f'unexpected libil2cpp.so (sha256 {sha}), expected original 2.9.6 arm64')
    assert data[RVA:RVA + 8] == ORIGINAL, data[RVA:RVA + 8].hex()
    data[RVA:RVA + 8] = PATCHED
    open(sys.argv[2], 'wb').write(data)
    print(f'UpToDate @ {RVA:#x}: {ORIGINAL.hex()} -> {PATCHED.hex()} ; wrote {sys.argv[2]}')


if __name__ == '__main__':
    main()
