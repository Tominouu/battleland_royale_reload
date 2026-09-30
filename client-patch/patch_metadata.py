#!/usr/bin/env python3
"""Redirect the PlayFab SDK of Battlelands 2.9.6 by patching global-metadata.dat string literals.

Same three literals Reborn changes, found by content (not index):

  "playfabapi.com"                           -> "https://<host>"
      PlayFabSettings uses a base URL starting with "http" verbatim instead of
      building "https://<TitleId>.playfabapi.com".
  ".playfabapi.com/Client/LinkCustomID"      -> "@<host>/Client/LinkCustomID"
  ".playfabapi.com/Client/LoginWithFacebook" -> "@<host>/Client/LoginWithFacebook"
      Hardcoded as "https://" + TitleId + literal; "@" turns the TitleId into URL userinfo.

Unlike Reborn (which overwrote three unrelated literals to make room), the new strings are
appended at the end of the file and only the literal table entries are repointed: IL2CPP v24
reads stringLiteralData + dataIndex without bounds checks and maps the whole file.
"""
import argparse
import struct
import sys

HEADER = struct.Struct('<IiIiIi')   # sanity, version, literalOffset, literalSize, dataOffset, dataSize
LITERAL = struct.Struct('<II')      # length, dataIndex


def patch(data: bytearray, host: str) -> list[str]:
    sanity, version, lit_off, lit_size, data_off, _ = HEADER.unpack_from(data, 0)
    if sanity != 0xFAB11BAF or version != 24:
        sys.exit(f'unexpected metadata header (sanity={sanity:#x}, version={version})')

    replacements = {
        b'playfabapi.com': f'https://{host}'.encode(),
        b'.playfabapi.com/Client/LinkCustomID': f'@{host}/Client/LinkCustomID'.encode(),
        b'.playfabapi.com/Client/LoginWithFacebook': f'@{host}/Client/LoginWithFacebook'.encode(),
    }
    found = {}
    for i in range(lit_size // LITERAL.size):
        length, index = LITERAL.unpack_from(data, lit_off + i * LITERAL.size)
        value = bytes(data[data_off + index:data_off + index + length])
        if value in replacements:
            found.setdefault(value, []).append(i)

    missing = [k.decode() for k in replacements if k not in found]
    if missing:
        sys.exit(f'literals not found (already patched, or not 2.9.6?): {missing}')

    log = []
    for old, new in replacements.items():
        new_index = len(data) - data_off
        data += new
        for i in found[old]:
            LITERAL.pack_into(data, lit_off + i * LITERAL.size, len(new), new_index)
            log.append(f'literal #{i}: {old.decode()!r} -> {new.decode()!r}')
    return log


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('metadata', help='original assets/bin/Data/Managed/Metadata/global-metadata.dat')
    ap.add_argument('host', help='backend host with a valid TLS certificate, e.g. b.203-0-113-10.sslip.io')
    ap.add_argument('-o', '--output', required=True)
    args = ap.parse_args()

    data = bytearray(open(args.metadata, 'rb').read())
    for line in patch(data, args.host):
        print(line)
    open(args.output, 'wb').write(data)
    print(f'wrote {args.output}')


if __name__ == '__main__':
    main()
