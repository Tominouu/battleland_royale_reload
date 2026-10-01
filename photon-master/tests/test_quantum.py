"""Quantum BitStream encoding and the config probe.

Run: python3 photon-master/tests/test_quantum.py -v
"""
import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import quantum  # noqa: E402

# Quantum Join sent by the real client in RaiseEvent 100 (build/normal-room-test/logs/normal-room.pcap)
CLIENT_JOIN = bytes.fromhex(
    '01480062 66ca666e 6e70cc5a c86272c8 5a68606a 6a5ac26a c2725acc c6c270c2'
    'c86a6462 64c6641c 00c8b8c0 b8c0b8c0 04000000 00000000 04000000 00'.replace(' ', ''))

# Hand-derived from the field encodings (not produced by BitWriter):
#   Joined        type 2 (bits 0-7), Confirmed 1 (bit 8), int[] present 1 (bit 9), count 1 (bits 10-25),
#                 element 0 (bits 26-57)
#   SessionConfig type 3 (bits 58-65), Requested 1 (bit 66), config null 1 (bit 67)
#   RuntimeConfig type 4 (bits 68-75), Requested 1 (bit 76), byte[] present 0 (bit 77); 2 padding bits
PROBE = bytes.fromhex('02 07 00 00 00 00 00 0c 4c 10')

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
# Client answer to the probe (build/quantum-probe-test/logs/c2s-event100-1793.bin): SessionConfig + RuntimeConfig
with open(os.path.join(FIXTURES, 'client-config-reply.bin'), 'rb') as f:
    CLIENT_CONFIG_REPLY = f.read()
# RuntimeConfig bytes of that answer (build/quantum-probe-test/logs/runtimeconfig-1707.bin)
with open(os.path.join(FIXTURES, 'runtimeconfig-1707.bin'), 'rb') as f:
    RUNTIME_CONFIG = f.read()
SESSION_CONFIG_BIT, SESSION_CONFIG_BITS = 9, 648   # after type (8) and Requested (1); null bit included


def simulation_start_from_capture():
    bits = quantum.read_raw_bits(CLIENT_CONFIG_REPLY, SESSION_CONFIG_BIT, SESSION_CONFIG_BITS)
    return quantum.simulation_start(RUNTIME_CONFIG, bits, SESSION_CONFIG_BITS)


class BitStreamTests(unittest.TestCase):
    def test_bits_are_lsb_first_without_alignment(self):
        w = quantum.BitWriter()
        w.write_bool(True)
        w.write(0x1234, 16)
        self.assertEqual(w.to_bytes(), bytes([0x69, 0x24, 0x00]))   # 1 | 0x1234 << 1
        r = quantum.BitReader(w.to_bytes())
        self.assertEqual((r.read_bool(), r.read(16)), (True, 0x1234))

    def test_bool(self):
        for value, expected in ((True, b'\x01'), (False, b'\x00')):
            w = quantum.BitWriter()
            w.write_bool(value)
            self.assertEqual(w.to_bytes(), expected)

    def test_int_array_presence_bit_is_one(self):
        w = quantum.BitWriter()
        w.write_int_array([0])
        self.assertEqual((w.bits, w.to_bytes()), (1 + 16 + 32, bytes.fromhex('03 00 00 00 00 00 00')))
        self.assertEqual(quantum.BitReader(w.to_bytes()).read_int_array(), [0])
        w = quantum.BitWriter()
        w.write_int_array(None)
        self.assertEqual((w.bits, w.to_bytes()), (1, b'\x00'))
        self.assertIsNone(quantum.BitReader(b'\x00').read_int_array())

    def test_int_array_values(self):
        w = quantum.BitWriter()
        w.write_int_array([1, -1, 0x7FFFFFFF])
        self.assertEqual(quantum.BitReader(w.to_bytes()).read_int_array(), [1, -1, 0x7FFFFFFF])

    def test_byte_array_presence_bit_is_one(self):
        w = quantum.BitWriter()
        w.write_byte_array(b'\xab')
        self.assertEqual(w.to_bytes(), bytes([0x03, 0x00, 0x56, 0x01]))   # 1 | 1 << 1 | 0xab << 17
        self.assertEqual(quantum.BitReader(w.to_bytes()).read_byte_array(), b'\xab')
        self.assertIsNone(quantum.BitReader(b'\x00').read_byte_array())

    def test_string_null_bit_is_one(self):
        self.assertIsNone(quantum.BitReader(b'\x01').read_string())
        self.assertEqual(quantum.BitReader(bytes([0x02, 0x00, 0x82, 0x00])).read_string(), 'A')   # 0 | 1 << 1 | 'A' << 17

    def test_session_config_null_bit_is_one(self):
        self.assertIsNone(quantum.BitReader(b'\x01').read_session_config())

    def test_session_config_v2_is_648_bits(self):
        self.assertEqual(1 + sum(bits for _, bits in quantum.SESSION_CONFIG_FIELDS_V2), 648)


class MessageTests(unittest.TestCase):
    def test_real_client_join_decodes(self):
        join, padding = quantum.decode_messages(CLIENT_JOIN)
        self.assertEqual(join, {'type': 1, 'name': 'Join', 'bit': 0, 'Id': '13e3778f-d19d-4055-a5a9-fca8ad5212c2',
                                'ProtocolVersion': '2.0.0.0', 'PlayerSlots': 1, 'InitialTick': 0,
                                'PlayerCount': 1, 'bits': 482})
        self.assertEqual(padding, {'padding_bits': 6})

    def test_probe_bytes(self):
        self.assertEqual(quantum.config_probe(), PROBE)

    def test_probe_is_three_concatenated_messages(self):
        joined, session, runtime, padding = quantum.decode_messages(quantum.config_probe())
        self.assertEqual((joined['name'], joined['Confirmed'], joined['PlayerSlots'], joined['bit'], joined['bits']),
                         ('Joined', True, [0], 0, 58))
        self.assertEqual((session['name'], session['Requested'], session['Config'], session['bit'], session['bits']),
                         ('SessionConfig', True, None, 58, 10))
        self.assertEqual((runtime['name'], runtime['Requested'], runtime['Config'], runtime['bit'], runtime['bits']),
                         ('RuntimeConfig', True, None, 68, 10))
        self.assertEqual(padding, {'padding_bits': 2})   # < 8: Serializer.ReadNext stops (CanRead(8))

    def test_client_answers_decode(self):
        # Shape of the expected answers: SessionConfig{Requested=false, config} + RuntimeConfig{false, bytes}
        w = quantum.BitWriter()
        w.write(quantum.MSG_SESSION_CONFIG, 8)
        w.write_bool(False)
        w.write_bool(False)
        for i, (name, bits) in enumerate(quantum.SESSION_CONFIG_FIELDS_V2):
            w.write(i % 2 if bits == 1 else i, bits)
        w.write(quantum.MSG_RUNTIME_CONFIG, 8)
        w.write_bool(False)
        w.write_byte_array(b'\x01\x02\x03')
        session, runtime, _ = quantum.decode_messages(w.to_bytes())
        self.assertEqual(session['Config']['PlayerCount'], 1)
        self.assertEqual(session['Config']['InputFixedSize'], len(quantum.SESSION_CONFIG_FIELDS_V2) - 1)
        self.assertEqual((runtime['Requested'], runtime['Config']), (False, b'\x01\x02\x03'))

    def test_captured_reply_layout(self):
        session, runtime, padding = quantum.decode_messages(CLIENT_CONFIG_REPLY)
        self.assertEqual(session['config_bits'], (SESSION_CONFIG_BIT, SESSION_CONFIG_BITS))
        self.assertEqual(runtime['Config'], RUNTIME_CONFIG)
        self.assertEqual((len(RUNTIME_CONFIG), padding), (1707, {'padding_bits': 5}))

    def test_double_is_little_endian_ieee754(self):
        w = quantum.BitWriter()
        w.write_double(1.0)
        self.assertEqual(w.to_bytes(), bytes.fromhex('00 00 00 00 00 00 f0 3f'))
        self.assertEqual(quantum.BitReader(w.to_bytes()).read_double(), 1.0)

    def test_unknown_type_stops_decoding(self):
        msgs = quantum.decode_messages(bytes([0x63, 0xFF]))
        self.assertEqual((len(msgs), msgs[0]['type'], msgs[0].get('undecoded')), (1, 0x63, True))


class SimulationStartTests(unittest.TestCase):
    def setUp(self):
        self.start = simulation_start_from_capture()
        self.reader = quantum.BitReader(self.start)

    def test_length_is_1800_bytes(self):
        # 8 + 1 + 64 + (1 + 16 + 1707 * 8) + 648 = 14394 bits
        self.assertEqual(len(self.start), 1800)

    def test_byte_aligned_prefix(self):
        # type 5 | Reconnect 0 + ServerTime 0.0 (bits 8-72) | presence 1 (bit 73), length 1707 (bits 74-89),
        # first RuntimeConfig bits: hand-derived, 0x6AB = 0b11010101011, RUNTIME_CONFIG[0] = 0xb1
        self.assertEqual(self.start[:12], bytes.fromhex('05 00 00 00 00 00 00 00 00 ae 1a c4'))

    def test_fields(self):
        r = self.reader
        self.assertEqual((r.read(8), r.read_bool(), r.read_double()), (5, False, 0.0))
        self.assertEqual((r.read_bool(), r.read(16)), (True, 1707))
        self.assertEqual(r.read_bytes(1707), RUNTIME_CONFIG)
        self.assertEqual(r.pos, 13746)
        self.assertEqual(r.read(SESSION_CONFIG_BITS),
                         quantum.read_raw_bits(CLIENT_CONFIG_REPLY, SESSION_CONFIG_BIT, SESSION_CONFIG_BITS))
        self.assertEqual(r.pos, 14394)

    def test_padding_is_six_zero_bits(self):
        self.reader.pos = 14394
        self.assertEqual(self.reader.read(6), 0)
        self.assertFalse(self.reader.can_read(1))

    def test_decodes_as_single_simulation_start(self):
        start, padding = quantum.decode_messages(self.start)
        session = quantum.decode_messages(CLIENT_CONFIG_REPLY)[0]['Config']
        self.assertEqual((start['name'], start['Reconnect'], start['ServerTime']), ('SimulationStart', False, 0.0))
        self.assertEqual((start['RuntimeConfig'], start['SessionConfig']), (RUNTIME_CONFIG, session))
        self.assertEqual((start['SessionConfig']['PlayerCount'], start['SessionConfig']['UpdateFPS']), (1, 30))
        self.assertEqual(padding, {'padding_bits': 6})

    def test_sha256(self):
        self.assertEqual(hashlib.sha256(self.start).hexdigest(),
                         'bdc664a12376eb65ed99adba866c65648a0d3837f750f729728e3518dfc91da1')

if __name__ == '__main__':
    unittest.main()
