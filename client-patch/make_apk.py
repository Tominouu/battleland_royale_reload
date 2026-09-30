#!/usr/bin/env python3
"""Build the experimental APK from the ORIGINAL 2.9.6 APK without apktool/zipalign/apksigner.

- every original entry is copied byte-for-byte (compressed data untouched), in original order;
- lib/arm64-v8a/libmain.so is renamed lib/arm64-v8a/libmain_orig.so (same bytes);
- our libmain.so is added as lib/arm64-v8a/libmain.so;
- global-metadata.dat is replaced by the patched copy;
- the old v1 signature files (META-INF/MANIFEST.MF, *.SF, *.RSA, *.DSA, *.EC) are dropped;
- STORED entries are 4-byte aligned (.so: 4096), as zipalign -p does (resources.arsc must be
  stored + aligned for targetSdk 30);
- signed with APK Signature Scheme v2 (RSA 2048 / SHA-256), enough for Android 7+ / Waydroid.

Needs the `cryptography` package. A test key is generated in --keydir if absent.
"""
import argparse
import hashlib
import os
import struct
import zipfile
import zlib
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

LIB = 'lib/arm64-v8a/'
METADATA = 'assets/bin/Data/Managed/Metadata/global-metadata.dat'
V1_SIG_SUFFIXES = ('.SF', '.RSA', '.DSA', '.EC')


# ---------------------------------------------------------------- zip

def is_v1_signature(name):
    return name.startswith('META-INF/') and '/' not in name[9:] and (
        name == 'META-INF/MANIFEST.MF' or name.upper().endswith(V1_SIG_SUFFIXES))


def raw_entry(src, info):
    """Compressed bytes of an existing entry, read straight from its local header."""
    src.seek(info.header_offset)
    hdr = src.read(30)
    assert hdr[:4] == b'PK\x03\x04', info.filename
    name_len, extra_len = struct.unpack('<HH', hdr[26:30])
    src.seek(info.header_offset + 30 + name_len + extra_len)
    return src.read(info.compress_size)


class Writer:
    def __init__(self, path):
        self.f = open(path, 'wb')
        self.central = []

    def add(self, name, method, crc, csize, usize, data, dostime, dosdate, ext_attr=0):
        name_b = name.encode()
        offset = self.f.tell()
        extra = b''
        if method == zipfile.ZIP_STORED:
            align = 4096 if name.endswith('.so') else 4
            data_start = offset + 30 + len(name_b)
            pad = (-(data_start + 6)) % align                 # 0xd935 alignment extra, as apksigner
            extra = struct.pack('<HHH', 0xd935, 2 + pad, align) + b'\0' * pad
        flags = 0x0800 if not name.isascii() else 0
        self.f.write(struct.pack('<IHHHHHIIIHH', 0x04034b50, 20, flags, method, dostime, dosdate,
                                 crc, csize, usize, len(name_b), len(extra)))
        self.f.write(name_b + extra + data)
        self.central.append(struct.pack('<IHHHHHHIIIHHHHHII', 0x02014b50, 0x0314, 20, flags, method,
                                        dostime, dosdate, crc, csize, usize, len(name_b), 0, 0, 0, 0,
                                        ext_attr, offset) + name_b)

    def close(self):
        cd_offset = self.f.tell()
        cd = b''.join(self.central)
        self.f.write(cd)
        n = len(self.central)
        self.f.write(struct.pack('<IHHHHIIH', 0x06054b50, 0, 0, n, n, len(cd), cd_offset, 0))
        self.f.close()


def dos_time(info):
    y, mo, d, h, mi, s = info.date_time
    return (h << 11) | (mi << 5) | (s // 2), ((y - 1980) << 9) | (mo << 5) | d


def new_entry_bytes(path, deflate=True):
    data = open(path, 'rb').read()
    crc = zlib.crc32(data)
    if deflate:
        c = zlib.compressobj(9, zlib.DEFLATED, -15)
        comp = c.compress(data) + c.flush()
        return zipfile.ZIP_DEFLATED, crc, comp, len(data)
    return zipfile.ZIP_STORED, crc, data, len(data)


def build_unsigned(original, out, libmain, metadata, extra=None):
    extra = dict(extra or {})
    log = []
    with zipfile.ZipFile(original) as z, open(original, 'rb') as src:
        names = [i.filename for i in z.infolist()]
        assert LIB + 'libmain.so' in names and METADATA in names
        assert LIB + 'libmain_orig.so' not in names, 'input already patched?'
        w = Writer(out)
        for info in z.infolist():
            name = info.filename
            if is_v1_signature(name):
                log.append(f'dropped   {name}')
                continue
            t, d = dos_time(info)
            if name == METADATA or name in extra:
                src_path = extra.pop(name, metadata)
                method, crc, data, usize = new_entry_bytes(src_path, info.compress_type == zipfile.ZIP_DEFLATED)
                w.add(name, method, crc, len(data), usize, data, t, d, info.external_attr)
                log.append(f'replaced  {name} ({info.file_size} -> {usize} bytes)')
                continue
            raw = raw_entry(src, info)
            if name == LIB + 'libmain.so':
                w.add(LIB + 'libmain_orig.so', info.compress_type, info.CRC, info.compress_size,
                      info.file_size, raw, t, d, info.external_attr)
                log.append(f'renamed   {name} -> {LIB}libmain_orig.so (bytes unchanged)')
                method, crc, data, usize = new_entry_bytes(libmain)
                w.add(name, method, crc, len(data), usize, data, t, d, info.external_attr)
                log.append(f'added     {name} (ours, {usize} bytes)')
                continue
            w.add(name, info.compress_type, info.CRC, info.compress_size, info.file_size, raw, t, d,
                  info.external_attr)
        w.close()
    assert not extra, f'--replace entries not in APK: {sorted(extra)}'
    return log


# ---------------------------------------------------------------- APK Signature Scheme v2

def lp(b):
    return struct.pack('<I', len(b)) + b


def chunked_digest(sections):
    chunks = []
    for sec in sections:
        for i in range(0, len(sec), 1 << 20):
            c = sec[i:i + (1 << 20)]
            chunks.append(hashlib.sha256(b'\xa5' + struct.pack('<I', len(c)) + c).digest())
    return hashlib.sha256(b'\x5a' + struct.pack('<I', len(chunks)) + b''.join(chunks)).digest()


def load_or_create_key(keydir):
    os.makedirs(keydir, exist_ok=True)
    kp, cp = os.path.join(keydir, 'test-key.pem'), os.path.join(keydir, 'test-cert.der')
    if not os.path.exists(kp):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Battlelands private test key')])
        now = datetime.now(timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=36500))
                .sign(key, hashes.SHA256()))
        open(kp, 'wb').write(key.private_bytes(serialization.Encoding.PEM,
                                               serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
        open(cp, 'wb').write(cert.public_bytes(serialization.Encoding.DER))
    key = serialization.load_pem_private_key(open(kp, 'rb').read(), None)
    return key, open(cp, 'rb').read()


def sign_v2(unsigned, out, keydir):
    apk = open(unsigned, 'rb').read()
    eocd = apk.rfind(b'PK\x05\x06')
    cd_size, cd_offset = struct.unpack_from('<II', apk, eocd + 12)
    entries, cd, eocd_bytes = apk[:cd_offset], apk[cd_offset:eocd], apk[eocd:]

    key, cert = load_or_create_key(keydir)
    algo = 0x0103   # RSASSA-PKCS1-v1_5 with SHA2-256
    digest = chunked_digest([entries, cd, eocd_bytes])
    signed_data = lp(lp(struct.pack('<I', algo) + lp(digest))) + lp(lp(cert)) + lp(b'')
    signature = key.sign(signed_data, padding.PKCS1v15(), hashes.SHA256())
    pubkey = key.public_key().public_bytes(serialization.Encoding.DER,
                                           serialization.PublicFormat.SubjectPublicKeyInfo)
    signer = lp(signed_data) + lp(lp(struct.pack('<I', algo) + lp(signature))) + lp(pubkey)
    v2_value = lp(lp(signer))

    pair = struct.pack('<I', 0x7109871a) + v2_value
    pairs = struct.pack('<Q', len(pair)) + pair
    block_size = len(pairs) + 8 + 16
    block = struct.pack('<Q', block_size) + pairs + struct.pack('<Q', block_size) + b'APK Sig Block 42'

    new_eocd = bytearray(eocd_bytes)
    struct.pack_into('<I', new_eocd, 16, cd_offset + len(block))
    with open(out, 'wb') as f:
        f.write(entries + block + cd + bytes(new_eocd))
    return hashlib.sha256(cert).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('original_apk')
    ap.add_argument('libmain', help='our libmain.so (arm64-v8a)')
    ap.add_argument('metadata', help='patched global-metadata.dat')
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--replace', action='append', default=[], metavar='ENTRY=FILE',
                    help='also replace an existing APK entry (e.g. lib/arm64-v8a/libil2cpp.so=patched.so)')
    ap.add_argument('--keydir', required=True, help='where the test signing key lives / is created')
    a = ap.parse_args()

    unsigned = a.output + '.unsigned'
    for line in build_unsigned(a.original_apk, unsigned, a.libmain, a.metadata,
                               [r.split('=', 1) for r in a.replace]):
        print(line)
    cert_sha = sign_v2(unsigned, a.output, a.keydir)
    os.remove(unsigned)
    print(f'signed (v2) {a.output}  cert SHA-256 {cert_sha}')


if __name__ == '__main__':
    main()
