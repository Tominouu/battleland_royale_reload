"""Quantum deterministic protocol messages (Photon.Deterministic.Protocol, protocol version 2.0.0.0).

Carried in Photon events/RaiseEvent code 100 (reliable protocol), parameter 245 = byte[]. The byte[] is a
Photon.Deterministic.BitStream: bits written LSB first (bit n of the stream is bit n%8 of byte n/8), no
alignment. Serializer.ReadNext reads messages while CanRead(8): [type:8][fields]... so trailing padding
must stay below 8 bits.

Field encodings (BitStream.Serialize overloads in libil2cpp 2.9.6):
  bool        1 bit, 1 = true
  int/uint    32 bits
  ushort      16 bits
  string      1 bit (1 = null), ushort length, UTF-8 bytes            (0x17CE144 / ReadString 0x17CE1D8)
  int[]       1 bit (1 = present), ushort count, 32 bits per element  (0x17CD554)
  byte[]      1 bit (1 = present), ushort length, bytes               (WriteByteArrayLengthPrefixed 0x17CD80C)
  double      64 bits: the 8 IEEE-754 little-endian bytes, byte 0 first (WriteDouble 0x17CE4DC / ReadDouble 0x17CE610)
  DeterministicSessionConfig  1 bit (1 = null), then fields           (0x17DD628)
"""

import struct

MSG_JOIN = 1
MSG_JOINED = 2
MSG_SESSION_CONFIG = 3
MSG_RUNTIME_CONFIG = 4
MSG_SIMULATION_START = 5
MSG_NAMES = {1: 'Join', 2: 'Joined', 3: 'SessionConfig', 4: 'RuntimeConfig', 5: 'SimulationStart',
             6: 'SimulationStop', 7: 'ClockCorrect', 8: 'TickChecksum', 9: 'TickChecksumError', 10: 'RttUpdate',
             11: 'SetPlayerData', 12: 'Disconnect', 13: 'FrameSnapshot', 14: 'Command',
             15: 'TickChecksumErrorFrameDump', 16: 'InputMissing'}

# DeterministicSessionConfig.Serialize for DeterministicProtocolVersions.V2_0_0_0 (GetEnum = 5):
# fields in wire order with their bit width (bool = 1); _BW_COMPAT_* fields are only sent for version 0.
SESSION_CONFIG_FIELDS_V2 = [
    ('BackgroundThreadPriority', 32), ('PlayerCount', 32),
    ('SkipRollbackWhenPossible', 1), ('RunInBackgroundThread', 1), ('ExposeVerifiedStatusInsideSimulation', 1),
    ('LockstepSimulation', 1), ('AggressiveSendMode', 1),
    ('InputDelayMin', 32), ('InputDelayMax', 32), ('InputDelayPingStart', 32),
    ('UpdateFPS', 32), ('ChecksumInterval', 32), ('RollbackWindow', 32), ('InputPacking', 32),
    ('InputHardTolerance', 32),
    ('InputRedundancyStagger', 32), ('InputRepeatMaxDistance', 32), ('SessionStartTimeout', 32),
    ('TimeCorrectionRate', 32), ('MinTimeCorrectionFrames', 32), ('MinOffsetCorrectionDiff', 32),
    ('TimeScaleMin', 32), ('TimeScalePingMin', 32), ('TimeScalePingMax', 32),
    ('ChecksumCrossPlatformDeterminism', 1),            # version >= 2
    ('InputFixedSizeEnabled', 1), ('InputFixedSize', 32),  # version > 2
]


class BitStreamError(Exception):
    pass


class BitWriter:
    def __init__(self):
        self.data = bytearray()
        self.bits = 0

    def write(self, value: int, count: int):
        for i in range(count):
            if self.bits % 8 == 0:
                self.data.append(0)
            if (value >> i) & 1:
                self.data[-1] |= 1 << (self.bits % 8)
            self.bits += 1

    def write_bool(self, value: bool):
        self.write(1 if value else 0, 1)

    def write_int_array(self, values: list[int] | None):
        self.write_bool(values is not None)
        if values is not None:
            self.write(len(values), 16)
            for v in values:
                self.write(v & 0xFFFFFFFF, 32)

    def write_double(self, value: float):
        for b in struct.pack('<d', value):
            self.write(b, 8)

    def write_byte_array(self, value: bytes | None):
        self.write_bool(value is not None)
        if value is not None:
            self.write(len(value), 16)
            for b in value:
                self.write(b, 8)

    def to_bytes(self) -> bytes:
        return bytes(self.data)


class BitReader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def can_read(self, count: int) -> bool:
        return self.pos + count <= len(self.data) * 8

    def read(self, count: int) -> int:
        if not self.can_read(count):
            raise BitStreamError(f'need {count} bits at bit {self.pos}, have {len(self.data) * 8 - self.pos}')
        value = 0
        for i in range(count):
            p = self.pos + i
            value |= ((self.data[p // 8] >> (p % 8)) & 1) << i
        self.pos += count
        return value

    def read_bool(self) -> bool:
        return self.read(1) == 1

    def read_int(self) -> int:
        value = self.read(32)
        return value - (1 << 32) if value & 0x80000000 else value

    def read_double(self) -> float:
        return struct.unpack('<d', self.read_bytes(8))[0]

    def read_bytes(self, count: int) -> bytes:
        return bytes(self.read(8) for _ in range(count))

    def read_string(self) -> str | None:
        if self.read_bool():
            return None
        return self.read_bytes(self.read(16)).decode('utf-8')

    def read_int_array(self) -> list[int] | None:
        if not self.read_bool():
            return None
        return [self.read_int() for _ in range(self.read(16))]

    def read_byte_array(self) -> bytes | None:
        if not self.read_bool():
            return None
        return self.read_bytes(self.read(16))

    def read_session_config(self) -> dict | None:
        if self.read_bool():
            return None
        return {name: (self.read_bool() if bits == 1 else self.read_int()) for name, bits in SESSION_CONFIG_FIELDS_V2}


def encode_joined(writer: BitWriter, confirmed: bool, player_slots: list[int] | None):
    writer.write(MSG_JOINED, 8)
    writer.write_bool(confirmed)
    writer.write_int_array(player_slots)


def encode_session_config_request(writer: BitWriter):
    """SessionConfig{Requested=true, Config=null}: the client answers with its local DeterministicSessionConfig."""
    writer.write(MSG_SESSION_CONFIG, 8)
    writer.write_bool(True)
    writer.write_bool(True)   # config == null


def encode_runtime_config_request(writer: BitWriter):
    """RuntimeConfig{Requested=true, Config=null}: the client answers with its local RuntimeConfig bytes."""
    writer.write(MSG_RUNTIME_CONFIG, 8)
    writer.write_bool(True)
    writer.write_byte_array(None)


def config_probe() -> bytes:
    """Joined{Confirmed, PlayerSlots=[0]} + SessionConfig{Requested} + RuntimeConfig{Requested}, one byte[]."""
    writer = BitWriter()
    encode_joined(writer, True, [0])
    encode_session_config_request(writer)
    encode_runtime_config_request(writer)
    return writer.to_bytes()


def read_raw_bits(data: bytes, start: int, count: int) -> int:
    """Bits [start, start+count) of a BitStream as an LSB-first integer, to copy them verbatim with BitWriter.write."""
    reader = BitReader(data)
    reader.pos = start
    return reader.read(count)


def simulation_start(runtime_config: bytes, session_config_bits: int, session_config_bit_count: int,
                     reconnect: bool = False, server_time: float = 0.0) -> bytes:
    """SimulationStart (SimulationStart.Serialize 0x24CFC1C): type 5, Reconnect, ServerTime, RuntimeConfig as a
    length-prefixed byte[], then the DeterministicSessionConfig bits copied verbatim (null bit included)."""
    writer = BitWriter()
    writer.write(MSG_SIMULATION_START, 8)
    writer.write_bool(reconnect)
    writer.write_double(server_time)
    writer.write_byte_array(runtime_config)
    writer.write(session_config_bits, session_config_bit_count)
    return writer.to_bytes()


def decode_messages(data: bytes) -> list[dict]:
    """Decodes every message like Serializer.ReadNext (while 8 bits remain). Unknown types stop decoding;
    the entry then carries the bit position so the raw bytes can be analysed."""
    reader = BitReader(data)
    messages = []
    while reader.can_read(8):
        start = reader.pos
        msg_type = reader.read(8)
        msg = {'type': msg_type, 'name': MSG_NAMES.get(msg_type, '?'), 'bit': start}
        try:
            if msg_type == MSG_JOIN:
                msg.update(Id=reader.read_string(), ProtocolVersion=reader.read_string(),
                           PlayerSlots=reader.read_int(), InitialTick=reader.read_int(), PlayerCount=reader.read_int())
            elif msg_type == MSG_JOINED:
                msg.update(Confirmed=reader.read_bool(), PlayerSlots=reader.read_int_array())
            elif msg_type == MSG_SESSION_CONFIG:
                msg['Requested'] = reader.read_bool()
                config_bit = reader.pos
                msg['Config'] = reader.read_session_config()
                msg['config_bits'] = (config_bit, reader.pos - config_bit)   # null bit included
            elif msg_type == MSG_RUNTIME_CONFIG:
                msg.update(Requested=reader.read_bool(), Config=reader.read_byte_array())
            elif msg_type == MSG_SIMULATION_START:
                msg.update(Reconnect=reader.read_bool(), ServerTime=reader.read_double(),
                           RuntimeConfig=reader.read_byte_array())
                config_bit = reader.pos
                msg['SessionConfig'] = reader.read_session_config()
                msg['config_bits'] = (config_bit, reader.pos - config_bit)
            else:
                msg['undecoded'] = True
                messages.append(msg)
                break
        except BitStreamError as e:
            msg['error'] = str(e)
            messages.append(msg)
            break
        msg['bits'] = reader.pos - start
        messages.append(msg)
    if messages and 'undecoded' not in messages[-1] and 'error' not in messages[-1]:
        messages.append({'padding_bits': len(data) * 8 - reader.pos})
    return messages


def describe_message(msg: dict) -> str:
    fields = {k: (f'byte[{len(v)}] {v.hex()}' if isinstance(v, bytes) else v) for k, v in msg.items()
              if k not in ('type', 'name')}
    return f"{msg.get('name', '')}({msg.get('type', '')}) {fields}" if 'type' in msg else str(fields)
