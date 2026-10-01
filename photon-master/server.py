#!/usr/bin/env python3
"""Minimal Photon MasterServer for Battlelands Royale 2.9.6 (PUN classic 1.92, Photon3Unity3D, TCP).

Scope: TCP framing, Init, ping, Diffie-Hellman key exchange (internal op 0), encrypted
OpAuthenticate (230) checked against battlelands-server (POST /internal/photon/validate), then keep
the connection alive. The Master answers CreateGame (227) with a room name and the GameServer address;
the GameServer answers CreateGame by entering the client as actor 1 (OperationResponse 227 + Join event 255)
and otherwise only logs what the client sends. No room manager. Quantum: only a config probe answers the
first Quantum Join (see handle_game_raise_event); no SimulationStart, no input (102) handling.

Wire format (capture build/photon-appid/logs/photon-4530.pcap + TPeer.SerializeOperationToMessage):
  framed:  FB | len:u32 BE (whole frame) | channel:u8 | 01 | F3 | msgType:u8 | body
  ping:    F0 | clientTime:u32 BE                              (client -> server, unframed)
  pong:    F0 | serverTime:u32 BE | clientTime:u32 BE          (server -> client, unframed)
msgType bit 0x80 = body encrypted. Serialization is Protocol16 (init carries protocol version 1.6).

Encryption (Photon.SocketServer.Security.DiffieHellmanCryptoProvider):
  Oakley 768-bit prime (RFC 2409 group 1), generator 22, 160-bit secret, public keys as minimal
  big-endian bytes; AES-256 key = SHA256(minimal big-endian shared secret); AES-CBC, zero IV, PKCS7.
"""
import argparse
import asyncio
import hashlib
import itertools
import json
import logging
import os
import secrets
import ssl
import struct
import time
import urllib.error
import urllib.parse
import urllib.request

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

import quantum

log = logging.getLogger('photon-master')

# --- framing -----------------------------------------------------------------------------------

FRAME_MAGIC = 0xFB
PING_MAGIC = 0xF0
MESSAGE_MAGIC = 0xF3
FRAME_HEADER = struct.Struct('>BIBB')   # magic, total length, channel, reliable flag
FRAME_MIN_LENGTH = FRAME_HEADER.size + 2  # + F3 + msgType
FRAME_MAX_LENGTH = 1 << 20

MSG_INIT = 0
MSG_INIT_RESPONSE = 1
MSG_OPERATION_REQUEST = 2
MSG_OPERATION_RESPONSE = 3
MSG_EVENT = 4
MSG_INTERNAL_OPERATION_REQUEST = 6
MSG_INTERNAL_OPERATION_RESPONSE = 7
MSG_ENCRYPTED = 0x80
MSG_NAMES = {0: 'Init', 1: 'InitResponse', 2: 'OperationRequest', 3: 'OperationResponse', 4: 'Event',
             6: 'InternalOperationRequest', 7: 'InternalOperationResponse'}

OP_INIT_ENCRYPTION = 0      # internal operation
OP_AUTHENTICATE = 230
OP_CREATE_GAME = 227
OP_JOIN_RANDOM_GAME = 225
OP_RAISE_EVENT = 253
PARAM_EVENT_CODE = 244
PARAM_DATA = 245
# Quantum event codes (QuantumNetworkCommunicator / DeterministicNetwork)
QUANTUM_EVENT_PROTOCOL = 100
QUANTUM_EVENT_INPUT = 102
# ErrorCode.NoRandomMatchFound; NetworkingPeer.OnOperationResponse (225) compares with 0x7FF8, then
# OnPhotonRandomJoinFailed -> LobbyController -> LobbyRunner.CreateNewRoom
RETURN_CODE_NO_RANDOM_MATCH_FOUND = 32760
PARAM_ROOM_NAME = 255
PARAM_ADDRESS = 230
PARAM_EXPECTED_USERS = 238
PARAM_ACTOR_NR = 254
PARAM_ACTOR_LIST = 252
PARAM_PLAYER_PROPERTIES = 249
PARAM_GAME_PROPERTIES = 248
EVENT_JOIN = 255
LOCAL_ACTOR_NR = 1
PARAM_APP_ID = 224
PARAM_AUTH_TYPE = 217
PARAM_AUTH_GET_PARAMETERS = 216
PARAM_USER_ID = 225
AUTH_TYPE_CUSTOM = 0
# ErrorCode.CustomAuthenticationFailed (0x7FFF - 12); NetworkingPeer.OnOperationResponse compares 230
# failures with 0x7FF3 and reports OnCustomAuthenticationFailed
RETURN_CODE_CUSTOM_AUTHENTICATION_FAILED = 32755
PARAM_CLIENT_KEY = 1
PARAM_SERVER_KEY = 1

AUTH_PARAM_NAMES = {220: 'AppVersion', 224: 'AppId', 210: 'Region', 225: 'UserId', 217: 'AuthType',
                    216: 'AuthGetParameters', 214: 'AuthPostData', 221: 'Token', 211: 'LobbyStats'}


class ProtocolError(Exception):
    pass


async def read_frame(reader: asyncio.StreamReader, magic: int) -> tuple[int, int, bytes]:
    """Read the rest of an FB frame whose magic byte was already consumed.

    Returns (channel, msgType, body). readexactly() handles fragmented and coalesced TCP reads.
    """
    rest = await reader.readexactly(FRAME_HEADER.size - 1)
    _, length, channel, _ = FRAME_HEADER.unpack(bytes([magic]) + rest)
    if not FRAME_MIN_LENGTH <= length <= FRAME_MAX_LENGTH:
        raise ProtocolError(f'invalid frame length {length}')
    payload = await reader.readexactly(length - FRAME_HEADER.size)
    if payload[0] != MESSAGE_MAGIC:
        raise ProtocolError(f'bad message magic {payload[0]:#04x} (expected F3)')
    return channel, payload[1], payload[2:]


def write_frame(writer: asyncio.StreamWriter, msg_type: int, body: bytes, channel: int = 0) -> bytes:
    payload = bytes([MESSAGE_MAGIC, msg_type]) + body
    frame = FRAME_HEADER.pack(FRAME_MAGIC, FRAME_HEADER.size + len(payload), channel, 1) + payload
    writer.write(frame)
    return frame


async def read_ping(reader: asyncio.StreamReader) -> int:
    """Read the clientTime of a ping whose F0 byte was already consumed."""
    return struct.unpack('>I', await reader.readexactly(4))[0]


def write_pong(writer: asyncio.StreamWriter, server_time: int, client_time: int) -> bytes:
    pong = struct.pack('>BII', PING_MAGIC, server_time, client_time)
    writer.write(pong)
    return pong


# --- Protocol16 --------------------------------------------------------------------------------

T_NULL, T_DICTIONARY, T_STRING_ARRAY, T_BYTE, T_CUSTOM = 0x2A, 0x44, 0x61, 0x62, 0x63
T_DOUBLE, T_EVENT, T_FLOAT, T_HASHTABLE, T_INTEGER = 0x64, 0x65, 0x66, 0x68, 0x69
T_SHORT, T_LONG, T_INT_ARRAY, T_BOOLEAN = 0x6B, 0x6C, 0x6E, 0x6F
T_STRING, T_BYTE_ARRAY, T_ARRAY, T_OBJECT_ARRAY = 0x73, 0x78, 0x79, 0x7A


class Protocol16Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def take(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise ProtocolError(f'Protocol16: need {n} bytes at {self.pos}, have {len(self.data) - self.pos}')
        chunk = self.data[self.pos:self.pos + n]
        self.pos += n
        return chunk

    def unpack(self, fmt: str):
        return struct.unpack('>' + fmt, self.take(struct.calcsize('>' + fmt)))[0]


def decode_protocol16_value(r: Protocol16Reader, type_code: int | None = None):
    if type_code is None:
        type_code = r.unpack('B')
    if type_code in (T_NULL, 0):
        return None
    if type_code == T_BYTE:
        return r.unpack('B')
    if type_code == T_BOOLEAN:
        return r.unpack('B') != 0
    if type_code == T_SHORT:
        return r.unpack('h')
    if type_code == T_INTEGER:
        return r.unpack('i')
    if type_code == T_LONG:
        return r.unpack('q')
    if type_code == T_FLOAT:
        return r.unpack('f')
    if type_code == T_DOUBLE:
        return r.unpack('d')
    if type_code == T_STRING:
        return r.take(r.unpack('H')).decode('utf-8')
    if type_code == T_BYTE_ARRAY:
        return r.take(r.unpack('i'))
    if type_code == T_INT_ARRAY:
        return [r.unpack('i') for _ in range(r.unpack('i'))]
    if type_code == T_STRING_ARRAY:
        return [decode_protocol16_value(r, T_STRING) for _ in range(r.unpack('h'))]
    if type_code == T_OBJECT_ARRAY:
        return [decode_protocol16_value(r) for _ in range(r.unpack('h'))]
    if type_code == T_ARRAY:
        count = r.unpack('h')
        element_type = r.unpack('B')
        return [decode_protocol16_value(r, element_type) for _ in range(count)]
    if type_code == T_HASHTABLE:
        return {decode_protocol16_value(r): decode_protocol16_value(r) for _ in range(r.unpack('h'))}
    if type_code == T_DICTIONARY:
        key_type, value_type = r.unpack('B'), r.unpack('B')
        result = {}
        for _ in range(r.unpack('h')):
            key = decode_protocol16_value(r, None if key_type in (0, T_NULL) else key_type)
            result[key] = decode_protocol16_value(r, None if value_type in (0, T_NULL) else value_type)
        return result
    if type_code == T_CUSTOM:
        custom_type = r.unpack('B')
        return ('custom', custom_type, r.take(r.unpack('h')))
    raise ProtocolError(f'Protocol16: unsupported type code {type_code:#04x} at {r.pos - 1}')


def decode_protocol16_parameters(r: Protocol16Reader) -> dict:
    params = {}
    for _ in range(r.unpack('h')):
        key = r.unpack('B')
        params[key] = decode_protocol16_value(r)
    return params


def decode_protocol16_operation_request(body: bytes) -> tuple[int, dict]:
    """OperationRequest body (after F3 msgType): opCode:u8 | count:i16 | (key:u8, typed value)*."""
    r = Protocol16Reader(body)
    op_code = r.unpack('B')
    params = decode_protocol16_parameters(r)
    if r.pos != len(body):
        raise ProtocolError(f'Protocol16: {len(body) - r.pos} trailing bytes after operation {op_code}')
    return op_code, params


class Protocol16Raw(bytes):
    """An already serialized typed Protocol16 value (type code included), emitted verbatim. Used to echo
    client data without losing Photon types (byte vs int keys, typed string arrays)."""


def decode_protocol16_parameters_raw(body: bytes) -> tuple[int, dict]:
    """OperationRequest body -> (opCode, {key: Protocol16Raw}) keeping each value's exact bytes and the wire order."""
    r = Protocol16Reader(body)
    op_code = r.unpack('B')
    params = {}
    for _ in range(r.unpack('h')):
        key = r.unpack('B')
        start = r.pos
        decode_protocol16_value(r)
        params[key] = Protocol16Raw(body[start:r.pos])
    return op_code, params


def encode_protocol16_value(value) -> bytes:
    if isinstance(value, Protocol16Raw):
        return bytes(value)
    if value is None:
        return bytes([T_NULL])
    if isinstance(value, bool):
        return struct.pack('>BB', T_BOOLEAN, int(value))
    if isinstance(value, (bytes, bytearray)):
        return struct.pack('>Bi', T_BYTE_ARRAY, len(value)) + bytes(value)
    if isinstance(value, str):
        data = value.encode('utf-8')
        return struct.pack('>BH', T_STRING, len(data)) + data
    if isinstance(value, int):
        return struct.pack('>Bi', T_INTEGER, value)
    if isinstance(value, list) and all(isinstance(v, int) and not isinstance(v, bool) for v in value):
        return struct.pack('>Bi', T_INT_ARRAY, len(value)) + b''.join(struct.pack('>i', v) for v in value)
    if isinstance(value, dict):   # Hashtable; keys and values typed individually
        return (struct.pack('>Bh', T_HASHTABLE, len(value))
                + b''.join(encode_protocol16_value(k) + encode_protocol16_value(v) for k, v in value.items()))
    raise TypeError(f'Protocol16 encoding not implemented for {type(value).__name__}')


def encode_protocol16_parameters(params: dict) -> bytes:
    out = struct.pack('>h', len(params))
    for key, value in params.items():
        out += bytes([key]) + encode_protocol16_value(value)
    return out


def encode_protocol16_event(event_code: int, params: dict) -> bytes:
    """EventData body: eventCode:u8 | parameters."""
    return bytes([event_code]) + encode_protocol16_parameters(params)


def encode_protocol16_operation_response(op_code: int, return_code: int, debug_message: str | None,
                                         params: dict) -> bytes:
    """OperationResponse body: opCode:u8 | returnCode:i16 | debugMessage (typed) | parameters."""
    return (struct.pack('>Bh', op_code, return_code) + encode_protocol16_value(debug_message)
            + encode_protocol16_parameters(params))


# --- Diffie-Hellman / AES -----------------------------------------------------------------------

# RFC 2409 Oakley group 1; same bytes as OakleyGroups in the client's global-metadata.dat
OAKLEY_PRIME_768 = int(
    'FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DD'
    'EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A63A3620FFFFFFFFFFFFFFFF', 16)
DH_GENERATOR = 22
DH_SECRET_BITS = 160


def int_to_minimal_be(value: int) -> bytes:
    """Photon.SocketServer.Numeric.BigInteger.GetBytes: big-endian, no leading zeros, 0 -> one byte."""
    return value.to_bytes(max(1, (value.bit_length() + 7) // 8), 'big')


def dh_generate_keypair() -> tuple[int, bytes]:
    secret = 0
    while secret < 2:
        secret = secrets.randbits(DH_SECRET_BITS)
    return secret, int_to_minimal_be(pow(DH_GENERATOR, secret, OAKLEY_PRIME_768))


def dh_compute_shared_secret(secret: int, client_public: bytes) -> bytes:
    peer = int.from_bytes(client_public, 'big')
    if not 1 < peer < OAKLEY_PRIME_768 - 1:
        raise ProtocolError('client public key out of range')
    return int_to_minimal_be(pow(peer, secret, OAKLEY_PRIME_768))


def derive_aes_key(shared_secret: bytes) -> bytes:
    return hashlib.sha256(shared_secret).digest()


def _aes(key: bytes) -> Cipher:
    return Cipher(algorithms.AES(key), modes.CBC(bytes(16)))


def decrypt_operation(key: bytes, ciphertext: bytes) -> bytes:
    if not ciphertext or len(ciphertext) % 16:
        raise ProtocolError(f'ciphertext length {len(ciphertext)} is not a positive multiple of 16')
    decryptor = _aes(key).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    try:
        return unpadder.update(padded) + unpadder.finalize()
    except ValueError as e:
        raise ProtocolError(f'invalid PKCS7 padding (sha256 padded={sha(padded)})') from e


def encrypt_operation(key: bytes, plaintext: bytes) -> bytes:
    padder = padding.PKCS7(128).padder()
    encryptor = _aes(key).encryptor()
    return encryptor.update(padder.update(plaintext) + padder.finalize()) + encryptor.finalize()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def describe_value(key: int, value) -> str:
    if isinstance(value, (bytes, bytearray)):
        return f'byte[{len(value)}] sha256={sha(value)}'
    return repr(value)


# --- custom authentication -----------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_VALIDATE_URL = 'https://192.168.240.1/internal/photon/validate'
DEFAULT_BACKEND_CA = os.path.join(REPO_ROOT, 'build', 'tls', 'ca.pem')


def parse_auth_get_parameters(query: str) -> tuple[str | None, str | None]:
    """AuthGetParameters 'username=<PlayFabId>&token=<token>' -> (username, token)."""
    values = urllib.parse.parse_qs(query or '', keep_blank_values=True)
    return values.get('username', [None])[0], values.get('token', [None])[0]


class BackendTokenValidator:
    """Calls battlelands-server POST /internal/photon/validate. Any failure rejects (fail closed)."""

    def __init__(self, url: str, cafile: str | None, timeout: float = 5.0):
        self.url = url
        self.timeout = timeout
        self.context = ssl.create_default_context(cafile=cafile) if url.startswith('https') else None

    def _post(self, payload: dict) -> dict:
        request = urllib.request.Request(self.url, data=json.dumps(payload).encode(), method='POST',
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=self.timeout, context=self.context) as response:
            return json.load(response)

    async def validate(self, token: str, playfab_id: str, app_id: str) -> tuple[bool, str]:
        try:
            result = await asyncio.to_thread(self._post, {'token': token, 'playFabId': playfab_id, 'appId': app_id})
        except (urllib.error.URLError, OSError, ValueError) as e:
            return False, f'backend unavailable: {e}'
        if result.get('valid') is True and result.get('playFabId') == playfab_id:
            return True, 'ok'
        return False, f"backend rejected: {result.get('reason', result)}"


# --- connection ---------------------------------------------------------------------------------

ROLE_MASTER = 'MASTER'
ROLE_GAME = 'GAME'


class PhotonConnection:
    """One client connection; Master and GameServer share framing, DH/AES and custom authentication."""

    def __init__(self, conn_id: int, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                 validator: BackendTokenValidator, role: str = ROLE_MASTER, game_server_address: str | None = None):
        self.id = conn_id
        self.validator = validator
        self.role = role
        self.game_server_address = game_server_address
        self.reader = reader
        self.writer = writer
        self.peer = writer.get_extra_info('peername')
        self.aes_key: bytes | None = None
        self.authenticated = False
        self.quantum_probe_sent = False
        self.started = time.monotonic()

    def log(self, level: int, tag: str, msg: str, *args):
        log.log(level, f'#%d [%s] {msg}', self.id, tag, *args)

    def server_time(self) -> int:
        return int((time.monotonic() - self.started) * 1000) & 0xFFFFFFFF

    async def run(self):
        self.log(logging.INFO, 'TCP', '%s connection from %s:%d', self.role, *self.peer[:2])
        try:
            while True:
                try:
                    first = (await self.reader.readexactly(1))[0]
                except asyncio.IncompleteReadError:
                    self.log(logging.INFO, 'TCP', 'closed by client')
                    return
                if first == PING_MAGIC:
                    await self.handle_ping(await read_ping(self.reader))
                elif first == FRAME_MAGIC:
                    channel, msg_type, body = await read_frame(self.reader, first)
                    self.log(logging.INFO, 'TCP', 'C>S frame type=%#04x (%s%s) channel=%d body=%d',
                             msg_type, MSG_NAMES.get(msg_type & 0x7F, '?'),
                             ', encrypted' if msg_type & MSG_ENCRYPTED else '', channel, len(body))
                    await self.dispatch(msg_type, body)
                else:
                    raise ProtocolError(f'bad magic byte {first:#04x} (expected FB or F0)')
                await self.writer.drain()
        except asyncio.IncompleteReadError as e:
            self.log(logging.WARNING, 'TCP', 'connection closed mid-message (%d of %s bytes)',
                     len(e.partial), e.expected)
        except ProtocolError as e:
            self.log(logging.ERROR, 'TCP', 'protocol error, closing: %s', e)
        except (ConnectionError, OSError) as e:
            self.log(logging.INFO, 'TCP', 'connection lost: %s', e)
        except Exception:
            log.exception('#%d unexpected error', self.id)
        finally:
            self.writer.close()
            self.log(logging.INFO, 'TCP', 'socket closed (authenticated=%s)', self.authenticated)

    def send(self, msg_type: int, body: bytes) -> bytes:
        frame = write_frame(self.writer, msg_type, body)
        self.log(logging.INFO, 'TCP', 'S>C frame type=%#04x (%s) length=%d', msg_type,
                 MSG_NAMES.get(msg_type & 0x7F, '?'), len(frame))
        self.log(logging.DEBUG, 'TCP', 'S>C hex=%s', frame.hex(' '))
        return frame

    async def dispatch(self, msg_type: int, body: bytes):
        encrypted = bool(msg_type & MSG_ENCRYPTED)
        base_type = msg_type & 0x7F
        if base_type == MSG_INIT and not encrypted:
            self.handle_init(body)
        elif base_type == MSG_INTERNAL_OPERATION_REQUEST and not encrypted:
            self.handle_internal_operation(body)
        elif base_type == MSG_OPERATION_REQUEST:
            await self.handle_operation(body, encrypted)
        else:
            self.log(logging.WARNING, 'TCP', 'unhandled message type %#04x, body=%d hex=%s', msg_type,
                     len(body), body[:64].hex(' '))

    def handle_init(self, body: bytes):
        self.log(logging.INFO, 'INIT', 'body=%d hex=%s', len(body), body.hex(' '))
        self.send(MSG_INIT_RESPONSE, b'\x00')

    async def handle_ping(self, client_time: int):
        server_time = self.server_time()
        write_pong(self.writer, server_time, client_time)
        self.log(logging.INFO, 'PING', 'clientTime=%d -> pong serverTime=%d', client_time, server_time)

    def handle_internal_operation(self, body: bytes):
        op_code, params = decode_protocol16_operation_request(body)
        if op_code != OP_INIT_ENCRYPTION:
            self.log(logging.WARNING, 'DH', 'unexpected internal operation %d params=%s', op_code,
                     {k: describe_value(k, v) for k, v in params.items()})
            return
        self.handle_init_encryption(params)

    def handle_init_encryption(self, params: dict):
        client_key = params.get(PARAM_CLIENT_KEY)
        if not isinstance(client_key, bytes):
            raise ProtocolError(f'InitEncryption without byte[] ClientKey (params {sorted(params)})')
        secret, server_key = dh_generate_keypair()
        shared = dh_compute_shared_secret(secret, client_key)
        self.aes_key = derive_aes_key(shared)
        self.log(logging.INFO, 'DH', 'client key=%d bytes, server key=%d bytes, shared=%d bytes, '
                 'sha256(aesKey)=%s', len(client_key), len(server_key), len(shared), sha(self.aes_key))
        body = encode_protocol16_operation_response(OP_INIT_ENCRYPTION, 0, None, {PARAM_SERVER_KEY: server_key})
        self.send(MSG_INTERNAL_OPERATION_RESPONSE, body)

    async def handle_operation(self, body: bytes, encrypted: bool):
        if encrypted:
            if self.aes_key is None:
                raise ProtocolError('encrypted operation before key exchange')
            tag = self.role if self.authenticated else 'AUTH'
            self.log(logging.INFO, tag, 'ciphertext length=%d sha256=%s', len(body), sha(body))
            try:
                plaintext = decrypt_operation(self.aes_key, body)
            except ProtocolError as e:
                self.log(logging.ERROR, tag, 'decryption failed: %s', e)
                return
            self.log(logging.INFO, tag, 'plaintext length=%d', len(plaintext))
            if not self.authenticated:
                self.log(logging.INFO, 'AUTH', 'plaintext hex=%s', plaintext.hex(' '))
        else:
            plaintext = body
        try:
            op_code, params = decode_protocol16_operation_request(plaintext)
        except ProtocolError as e:
            self.log(logging.ERROR, 'TCP', 'cannot decode operation: %s (first bytes %s)', e, plaintext[:32].hex(' '))
            return
        if op_code == OP_AUTHENTICATE and not self.authenticated:
            await self.handle_authenticate(params, encrypted)
            return
        self.log(logging.INFO, self.role, 'post-auth operation opcode=%d length=%d encrypted=%s params=%s',
                 op_code, len(plaintext), encrypted, {k: describe_value(k, v) for k, v in params.items()})
        if self.role == ROLE_MASTER and self.authenticated and op_code == OP_JOIN_RANDOM_GAME:
            self.handle_join_random_game()
        elif self.role == ROLE_MASTER and self.authenticated and op_code == OP_CREATE_GAME:
            self.handle_create_game(params)
        elif self.role == ROLE_GAME and self.authenticated and op_code == OP_CREATE_GAME:
            self.handle_game_create_game(plaintext)
        elif self.role == ROLE_GAME and self.authenticated and op_code == OP_RAISE_EVENT:
            self.handle_game_raise_event(params)

    def handle_join_random_game(self):
        """No room is ever open for joining: answer 32760 so the client falls back to CreateNewRoom (227)."""
        self.send(MSG_OPERATION_RESPONSE, encode_protocol16_operation_response(
            OP_JOIN_RANDOM_GAME, RETURN_CODE_NO_RANDOM_MATCH_FOUND, None, {}))
        self.log(logging.INFO, 'MASTER', 'JoinRandomRoom -> NO_MATCH')

    def handle_create_game(self, params: dict):
        """Master CreateGame: NetworkingPeer.OnOperationResponse (227, MasterServer) reads 255 RoomName and
        230 GameServer address, then DisconnectToReconnect. Room options are only sent to the GameServer."""
        self.log(logging.INFO, 'MASTER', 'CreateGame accepted expectedUsers=%s', params.get(PARAM_EXPECTED_USERS))
        room_name = 'tutorial-' + secrets.token_hex(4)
        self.send(MSG_OPERATION_RESPONSE, encode_protocol16_operation_response(
            OP_CREATE_GAME, 0, None, {PARAM_ROOM_NAME: room_name, PARAM_ADDRESS: self.game_server_address}))
        self.log(logging.INFO, 'MASTER', 'CreateGame response room=%s gameServer=%s', room_name, self.game_server_address)

    def handle_game_create_game(self, plaintext: bytes):
        """GameServer CreateGame: the client becomes actor 1 of the room it asked for.

        NetworkingPeer.GameEnteredOnGameServer reads 254 ActorNr (required), 252 ActorList, 249 actor properties
        (Hashtable actorNr -> properties, ReadoutProperties) and 248 game properties; OnJoinedRoom is only sent
        when the Join event 255 for the local actor arrives (NetworkingPeer.OnEvent)."""
        _, raw = decode_protocol16_parameters_raw(plaintext)
        self.room = raw   # 255 RoomName, 238, 249, 248, 250, 241, 232, 235, 236, 204, 239, 191 as received
        player_properties = raw.get(PARAM_PLAYER_PROPERTIES, Protocol16Raw(encode_protocol16_value({})))
        game_properties = raw.get(PARAM_GAME_PROPERTIES, Protocol16Raw(encode_protocol16_value({})))
        room_name = decode_protocol16_value(Protocol16Reader(raw[PARAM_ROOM_NAME])) if PARAM_ROOM_NAME in raw else None
        self.log(logging.INFO, 'GAME', 'CreateGame room=%s received keys=%s', room_name, list(raw))
        response = encode_protocol16_operation_response(OP_CREATE_GAME, 0, None, {
            PARAM_ACTOR_NR: LOCAL_ACTOR_NR,
            PARAM_ACTOR_LIST: [LOCAL_ACTOR_NR],
            PARAM_PLAYER_PROPERTIES: {LOCAL_ACTOR_NR: player_properties},
            PARAM_GAME_PROPERTIES: game_properties,
        })
        frame = self.send(MSG_OPERATION_RESPONSE, response)
        self.log(logging.INFO, 'GAME', 'CreateGame response actor=%d hex=%s', LOCAL_ACTOR_NR, frame.hex(' '))
        event = encode_protocol16_event(EVENT_JOIN, {
            PARAM_ACTOR_NR: LOCAL_ACTOR_NR,
            PARAM_ACTOR_LIST: [LOCAL_ACTOR_NR],
            PARAM_PLAYER_PROPERTIES: player_properties,
        })
        frame = self.send(MSG_EVENT, event)
        self.log(logging.INFO, 'GAME', 'Join event sent actor=%d hex=%s', LOCAL_ACTOR_NR, frame.hex(' '))

    def handle_game_raise_event(self, params: dict):
        """Logs Quantum traffic (100 protocol, 101/102 input) and answers the first Quantum Join with one
        protocol event: Joined{Confirmed, PlayerSlots=[0]} + SessionConfig{Requested} + RuntimeConfig{Requested},
        so the client sends back its own configurations. Nothing else is sent (no SimulationStart)."""
        code, data = params.get(PARAM_EVENT_CODE), params.get(PARAM_DATA)
        if code not in (QUANTUM_EVENT_PROTOCOL, 101, QUANTUM_EVENT_INPUT) or not isinstance(data, bytes):
            return
        self.log(logging.INFO, 'QUANTUM', 'C>S event %d byte[%d] hex=%s', code, len(data), data.hex())
        if code != QUANTUM_EVENT_PROTOCOL:
            return
        messages = quantum.decode_messages(data)
        for msg in messages:
            self.log(logging.INFO, 'QUANTUM', 'C>S   %s', quantum.describe_message(msg))
        if self.quantum_probe_sent or not messages or messages[0].get('type') != quantum.MSG_JOIN:
            return
        probe = quantum.config_probe()
        self.log(logging.INFO, 'QUANTUM', 'S>C probe event %d byte[%d] hex=%s', QUANTUM_EVENT_PROTOCOL,
                 len(probe), probe.hex())
        for msg in quantum.decode_messages(probe):
            self.log(logging.INFO, 'QUANTUM', 'S>C   %s', quantum.describe_message(msg))
        # NetworkingPeer.OnEvent reads 254 (sender) only if present; the communicator ignores the sender
        frame = self.send(MSG_EVENT, encode_protocol16_event(QUANTUM_EVENT_PROTOCOL, {PARAM_DATA: probe}))
        self.quantum_probe_sent = True
        self.log(logging.INFO, 'QUANTUM', 'S>C probe frame hex=%s', frame.hex(' '))

    async def handle_authenticate(self, params: dict, encrypted: bool):
        self.log(logging.INFO, 'AUTH', 'OpAuthenticate encrypted=%s, %d parameters', encrypted, len(params))
        for key, value in params.items():
            self.log(logging.INFO, 'AUTH', '  %d %s = %s', key, AUTH_PARAM_NAMES.get(key, '?'), describe_value(key, value))
        valid, reason, user_id = await self.check_custom_authentication(params)
        if not valid:
            self.log(logging.WARNING, 'AUTH', 'rejected (%s) -> OperationResponse 230 ReturnCode=%d',
                     reason, RETURN_CODE_CUSTOM_AUTHENTICATION_FAILED)
            self.send(MSG_OPERATION_RESPONSE, encode_protocol16_operation_response(
                OP_AUTHENTICATE, RETURN_CODE_CUSTOM_AUTHENTICATION_FAILED, 'Custom authentication failed', {}))
            return
        # ReturnCode 0 and UserId (225) = validated PlayFabId: NetworkingPeer copies it into AuthValues.UserId
        # and PhotonPlayer.UserId (PlayerInfoManager.ApplyPlayerProps rejects an empty UserId).
        # No Token/NickName/EncryptionData.
        self.send(MSG_OPERATION_RESPONSE, encode_protocol16_operation_response(
            OP_AUTHENTICATE, 0, None, {PARAM_USER_ID: user_id}))
        self.authenticated = True
        self.log(logging.INFO, 'AUTH', 'accepted -> OperationResponse 230 ReturnCode=0 UserId=%s sent in clear', user_id)

    async def check_custom_authentication(self, params: dict) -> tuple[bool, str, str | None]:
        """Returns (valid, reason, PlayFabId); the PlayFabId is the username confirmed by the backend."""
        if params.get(PARAM_AUTH_TYPE) != AUTH_TYPE_CUSTOM:
            return False, f'AuthType {params.get(PARAM_AUTH_TYPE)!r} is not Custom', None
        query = params.get(PARAM_AUTH_GET_PARAMETERS)
        if not isinstance(query, str):
            return False, 'no AuthGetParameters', None
        username, token = parse_auth_get_parameters(query)
        app_id = params.get(PARAM_APP_ID)
        if not username or not token or not isinstance(app_id, str):
            return False, 'missing username, token or AppId', None
        valid, reason = await self.validator.validate(token, username, app_id)
        self.log(logging.INFO, 'AUTH', 'backend validation username=%s appId=%s -> %s', username, app_id, reason)
        return valid, reason, username if valid else None


class PhotonTCPServer:
    def __init__(self, host: str, port: int, validator: BackendTokenValidator, role: str = ROLE_MASTER,
                 game_server_address: str | None = None, ids: itertools.count | None = None):
        self.host = host
        self.port = port
        self.validator = validator
        self.role = role
        self.game_server_address = game_server_address
        self.ids = ids or itertools.count(1)

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        await PhotonConnection(next(self.ids), reader, writer, self.validator, self.role,
                               self.game_server_address).run()

    async def serve(self):
        server = await asyncio.start_server(self.handle, self.host, self.port)
        log.info('[TCP] %s listening on %s', self.role, ', '.join(str(s.getsockname()) for s in server.sockets))
        async with server:
            await server.serve_forever()


async def serve_master_and_game(host: str, master_port: int, game_port: int, game_server_address: str,
                                validator: BackendTokenValidator):
    ids = itertools.count(1)   # shared, so #N is unique across both listeners
    await asyncio.gather(
        PhotonTCPServer(host, master_port, validator, ROLE_MASTER, game_server_address, ids).serve(),
        PhotonTCPServer(host, game_port, validator, ROLE_GAME, None, ids).serve())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--host', default='0.0.0.0')
    ap.add_argument('--port', type=int, default=4530)
    ap.add_argument('--game-port', type=int, default=4531)
    ap.add_argument('--game-address', default='192.168.240.1:4531',
                    help='GameServer address returned to clients in CreateGame (default %(default)s)')
    ap.add_argument('--validate-url', default=DEFAULT_VALIDATE_URL,
                    help='battlelands-server token validation endpoint (default %(default)s)')
    ap.add_argument('--backend-ca', default=DEFAULT_BACKEND_CA,
                    help='CA certificate of the backend TLS certificate (default %(default)s)')
    ap.add_argument('-v', '--verbose', action='store_true', help='also log every outgoing frame in hex')
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(asctime)s.%(msecs)03d %(message)s', datefmt='%H:%M:%S')
    try:
        validator = BackendTokenValidator(args.validate_url, args.backend_ca)
        log.info('[AUTH] custom authentication via %s', args.validate_url)
        asyncio.run(serve_master_and_game(args.host, args.port, args.game_port, args.game_address, validator))
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
