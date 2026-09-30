#!/usr/bin/env python3
"""Experimental: neutralize the Firebase Analytics wrappers (2.9.6 arm64 only).

Without Google Play Services, the first access to Firebase.Analytics.FirebaseAnalytics throws
(TypeInitializationException, then ApplicationException "internal::IsInitialized()"), which
restarts the game from GameLoader.LoadingRoutine. These four void FuturePlay methods are the only
game code touching that type; each gets a RET as first instruction (4 bytes, revert = restore).

Apply on top of the GooglePlayServicesChecker-patched libil2cpp.so (patch_il2cpp_gps.py).
"""
import sys

RET = bytes.fromhex('c0035fd6')

# RVA, method, original first instruction
PATCHES = [
    (0xF42E24, 'FuturePlay.AnalyticsService.StartUp', 'f44fbea9'),        # stp x20, x19, [sp, #-0x20]!
    (0x10372B8, 'FuturePlay.GameAnalytics.SetUserProperties', 'ffc301d1'),  # sub sp, sp, #0x70
    (0xF42F40, 'FuturePlay.AnalyticsService.TrackEvent', 'f50f1df8'),      # str x21, [sp, #-0x30]!
    (0xF2DA94, 'FuturePlay.CombatAnalytics.TrackEvent', 'f657bda9'),       # stp x22, x21, [sp, #-0x30]!
]


def main():
    if len(sys.argv) != 3:
        sys.exit('usage: patch_il2cpp_analytics.py <libil2cpp.so> <output>')
    data = bytearray(open(sys.argv[1], 'rb').read())
    for rva, name, original in PATCHES:
        found = data[rva:rva + 4].hex()
        if found != original:
            sys.exit(f'{name} @ {rva:#x}: expected {original}, found {found}')
        data[rva:rva + 4] = RET
        print(f'{name} @ {rva:#x}: {original} -> {RET.hex()}')
    open(sys.argv[2], 'wb').write(data)
    print(f'wrote {sys.argv[2]}')


if __name__ == '__main__':
    main()
