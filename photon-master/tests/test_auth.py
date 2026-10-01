"""OpAuthenticate -> backend validation, end to end over TCP with a fake backend.

Run: python3 photon-master/tests/test_auth.py -v
The synthetic client reproduces the real client's sequence (Init, DH, encrypted OpAuthenticate with the
parameters observed in build/photon-master-test) using its own framing/crypto code.
"""
import asyncio
import hashlib
import json
import os
import secrets
import struct
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import quantum  # noqa: E402
import server  # noqa: E402

APP_ID = '774b10b9-5bfb-48a7-9971-55300fc0d4bd'
PLAYFAB_ID = '95B0723D9D844E0B'
TOKEN = '69efd82aaa484c7881c03e60fdf8cdd8'
P = server.OAKLEY_PRIME_768


class FakeBackend(BaseHTTPRequestHandler):
    """Same contract as battlelands-server /internal/photon/validate for a single known token."""
    calls = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        FakeBackend.calls.append(body)
        if body == {'token': TOKEN, 'playFabId': PLAYFAB_ID, 'appId': APP_ID}:
            result = {'valid': True, 'playFabId': PLAYFAB_ID}
        else:
            result = {'valid': False, 'reason': 'unknown token'}
        data = json.dumps(result).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def frame(msg_type, body):
    payload = bytes([0xF3, msg_type]) + body
    return struct.pack('>BIBB', 0xFB, 7 + len(payload), 0, 1) + payload


def p16_string(value):
    data = value.encode()
    return b's' + struct.pack('>H', len(data)) + data


async def read_frame(reader):
    header = await reader.readexactly(7)
    assert header[0] == 0xFB
    return await reader.readexactly(struct.unpack('>I', header[1:5])[0] - 7)


async def connect_and_authenticate(port, auth_params):
    """Init, DH, encrypted OpAuthenticate; returns (reader, writer, OperationResponse 230 payload)."""
    reader, writer = await asyncio.open_connection('127.0.0.1', port)
    writer.write(frame(0, bytes.fromhex('0106 1e 41 02 08 00') + b'LoadBalancing'.ljust(32, b'\0')))
    assert await read_frame(reader) == b'\xf3\x01\x00'
    secret = secrets.randbits(160)
    public = pow(22, secret, P)
    public_bytes = public.to_bytes((public.bit_length() + 7) // 8, 'big')
    writer.write(frame(6, b'\x00\x00\x01\x01x' + struct.pack('>i', len(public_bytes)) + public_bytes))
    response = await read_frame(reader)
    server_key = response[14:]
    shared = pow(int.from_bytes(server_key, 'big'), secret, P)
    key = hashlib.sha256(shared.to_bytes((shared.bit_length() + 7) // 8, 'big')).digest()
    plaintext = b'\xe6' + struct.pack('>h', len(auth_params)) + b''.join(bytes([k]) + v for k, v in auth_params)
    padder = padding.PKCS7(128).padder()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(bytes(16))).encryptor()
    writer.write(frame(0x82, encryptor.update(padder.update(plaintext) + padder.finalize()) + encryptor.finalize()))
    return reader, writer, await read_frame(reader)


async def authenticate(port, auth_params):
    """Returns the OperationResponse 230 payload (after F3 03) and whether the socket stays open."""
    reader, writer, auth_response = await connect_and_authenticate(port, auth_params)
    writer.write(b'\xf0\x00\x00\x00\x01')
    pong = await reader.readexactly(9)
    writer.close()
    return auth_response, pong[0] == 0xF0


def real_client_params(username=PLAYFAB_ID, token=TOKEN, app_id=APP_ID, auth_type=b'b\x00'):
    """The 5 parameters the real client sent (build/photon-master-test, 2026-10-01)."""
    return [(220, p16_string('2.9.6_release_1.92')), (224, p16_string(app_id)), (210, p16_string('eu')),
            (217, auth_type), (216, p16_string(f'username={username}&token={token}'))]


# ReturnCode 0, DebugMessage null, 225 UserId = PlayFabId
SUCCESS = bytes.fromhex('f3 03 e6 0000 2a 0001 e1') + p16_string(PLAYFAB_ID)
GAME_SERVER_ADDRESS = '192.168.240.1:4531'
# CreateGame as sent by the real client to the Master (build/matchmaking-227-test): only 238 ExpectedUsers
CREATE_GAME_ON_MASTER = (bytes.fromhex('e3 0001 ee 79 0001 73') + struct.pack('>H', len(PLAYFAB_ID))
                         + PLAYFAB_ID.encode())


# CreateGame as sent by the real client to the GameServer (build/gameserver-test/logs/gameserver.pcap, 09:45:11.533)
CREATE_GAME_ON_GAME_SERVER = bytes.fromhex(
    'e3000cff730011747574 6f7269616c2d33613634623836 31ee790001730010394141383931424441314630344632 43'
    'f9680002730002746579000473001039414138393142444131463034463243000000000000 62ff730000'
    'fa6f01f868000762fd6f0062fe6f0162fa79000373000174000163000167730001747300037473 30'
    '7300016 36f00730001677300 0062ff6201f16f00e86f01eb6900000bb8ec69000003e8cc790001'
    '73000d5175616e74756d506c7567696eef6f01bf6900000009'.replace(' ', ''))


# JoinRandomRoom as sent by the real client (build/normal-mm-test/logs2/normal-mm.pcap)
JOIN_RANDOM_ON_MASTER = (bytes.fromhex('e1 0002 f8 68 0003 73 0001 74 73 0003 747331 73 0001 63 6f 00'
                                       ' 73 0001 67 73 0000 ee 79 0001 73') + struct.pack('>H', len(PLAYFAB_ID))
                         + PLAYFAB_ID.encode())


# RaiseEvent 253 carrying the Quantum Join, as sent by the real client (build/normal-room-test/logs/normal-room.pcap):
# 244 EventCode = (byte)100, 245 = byte[61] BitStream, 252 TargetActors = int[]{0}
QUANTUM_JOIN = bytes.fromhex(
    '01480062 66ca666e 6e70cc5a c86272c8 5a68606a 6a5ac26a c2725acc c6c270c2'
    'c86a6462 64c6641c 00c8b8c0 b8c0b8c0 04000000 00000000 04000000 00'.replace(' ', ''))
RAISE_EVENT_QUANTUM_JOIN = (bytes.fromhex('fd 0003 f4 62 64 f5 78 0000003d') + QUANTUM_JOIN
                            + bytes.fromhex('fc 79 0001 69 00000000'))
QUANTUM_PROBE = bytes.fromhex('02 07 00 00 00 00 00 0c 4c 10')
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
with open(os.path.join(FIXTURES, 'client-config-reply.bin'), 'rb') as f:
    CLIENT_CONFIG_REPLY = f.read()   # SessionConfig + RuntimeConfig in one byte[] (real client)
with open(os.path.join(FIXTURES, 'runtimeconfig-1707.bin'), 'rb') as f:
    RUNTIME_CONFIG = f.read()
SIMULATION_START_SHA256 = 'bdc664a12376eb65ed99adba866c65648a0d3837f750f729728e3518dfc91da1'


def raise_event(code, data):
    return bytes.fromhex('fd 0003 f4 62') + bytes([code]) + b'\xf5\x78' + struct.pack('>i', len(data)) + data \
        + bytes.fromhex('fc 79 0001 69 00000000')


def decode_event(payload):
    """F3 04 | eventCode | parameters -> (eventCode, params)."""
    assert payload[:2] == b'\xf3\x04', payload[:2]
    r = server.Protocol16Reader(payload[2:])
    code = r.unpack('B')
    params = server.decode_protocol16_parameters(r)
    assert r.pos == len(payload) - 2
    return code, params


def decode_operation_response(payload):
    """F3 03 | opCode | returnCode | debugMessage | parameters -> (opCode, returnCode, debug, params)."""
    assert payload[:2] == b'\xf3\x03', payload[:2]
    r = server.Protocol16Reader(payload[2:])
    op_code, return_code = r.unpack('B'), r.unpack('h')
    debug = server.decode_protocol16_value(r)
    params = server.decode_protocol16_parameters(r)
    assert r.pos == len(payload) - 2
    return op_code, return_code, debug, params
FAILURE = bytes.fromhex('f3 03 e6 7ff3') + p16_string('Custom authentication failed') + b'\x00\x00'


class AuthenticateTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = ThreadingHTTPServer(('127.0.0.1', 0), FakeBackend)
        threading.Thread(target=cls.backend.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.backend.shutdown()

    async def asyncSetUp(self):
        FakeBackend.calls.clear()
        await self.start(f'http://127.0.0.1:{self.backend.server_port}/internal/photon/validate')

    async def start(self, url):
        validator = server.BackendTokenValidator(url, None, timeout=2)
        master = server.PhotonTCPServer('127.0.0.1', 0, validator, server.ROLE_MASTER, GAME_SERVER_ADDRESS)
        game = server.PhotonTCPServer('127.0.0.1', 0, validator, server.ROLE_GAME, runtime_config=RUNTIME_CONFIG)
        self.tcp = await asyncio.start_server(master.handle, '127.0.0.1', 0)
        self.game_tcp = await asyncio.start_server(game.handle, '127.0.0.1', 0)
        self.port = self.tcp.sockets[0].getsockname()[1]
        self.game_port = self.game_tcp.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        for tcp in (self.tcp, self.game_tcp):
            tcp.close()
            await tcp.wait_closed()

    async def test_valid_token_gets_unchanged_success_response(self):
        response, alive = await authenticate(self.port, real_client_params())
        self.assertEqual(response, SUCCESS)
        self.assertTrue(alive)
        self.assertEqual(FakeBackend.calls, [{'token': TOKEN, 'playFabId': PLAYFAB_ID, 'appId': APP_ID}])

    async def test_unknown_token_rejected(self):
        response, _ = await authenticate(self.port, real_client_params(token='0' * 32))
        self.assertEqual(response, FAILURE)

    async def test_wrong_playfab_id_rejected(self):
        response, _ = await authenticate(self.port, real_client_params(username='0000000000000000'))
        self.assertEqual(response, FAILURE)

    async def test_wrong_app_id_rejected(self):
        response, _ = await authenticate(self.port, real_client_params(app_id='2fd21053-1cdf-4067-887c-b83edd1a1af4'))
        self.assertEqual(response, FAILURE)

    async def test_non_custom_auth_type_rejected_without_backend_call(self):
        response, _ = await authenticate(self.port, real_client_params(auth_type=b'b\xff'))
        self.assertEqual(response, FAILURE)
        self.assertEqual(FakeBackend.calls, [])

    async def test_missing_auth_parameters_rejected(self):
        response, _ = await authenticate(self.port, real_client_params()[:4])
        self.assertEqual(response, FAILURE)
        self.assertEqual(FakeBackend.calls, [])

    async def test_backend_down_rejected(self):
        await self.asyncTearDown()
        await self.start('http://127.0.0.1:9/internal/photon/validate')
        response, _ = await authenticate(self.port, real_client_params())
        self.assertEqual(response, FAILURE)

    async def test_master_create_game_returns_room_and_game_server(self):
        reader, writer, _ = await connect_and_authenticate(self.port, real_client_params())
        writer.write(frame(2, CREATE_GAME_ON_MASTER))
        op_code, return_code, debug, params = decode_operation_response(await read_frame(reader))
        writer.close()
        self.assertEqual((op_code, return_code, debug), (227, 0, None))
        self.assertEqual(sorted(params), [230, 255])
        self.assertRegex(params[255], r'^tutorial-[0-9a-f]{8}$')
        self.assertEqual(params[230], GAME_SERVER_ADDRESS)

    async def test_master_create_game_room_names_differ(self):
        names = set()
        for _ in range(2):
            reader, writer, _ = await connect_and_authenticate(self.port, real_client_params())
            writer.write(frame(2, CREATE_GAME_ON_MASTER))
            names.add(decode_operation_response(await read_frame(reader))[3][255])
            writer.close()
        self.assertEqual(len(names), 2)

    async def test_master_ignores_create_game_before_authentication(self):
        reader, writer = await asyncio.open_connection('127.0.0.1', self.port)
        writer.write(frame(2, CREATE_GAME_ON_MASTER) + b'\xf0\x00\x00\x00\x01')
        self.assertEqual((await reader.readexactly(9))[0], 0xF0)   # only the pong comes back
        writer.close()

    async def test_game_server_init_dh_auth_returns_user_id(self):
        reader, writer, response = await connect_and_authenticate(self.game_port, real_client_params())
        self.assertEqual(response, SUCCESS)
        self.assertEqual(decode_operation_response(response)[3], {225: PLAYFAB_ID})
        writer.close()
        self.assertEqual(FakeBackend.calls, [{'token': TOKEN, 'playFabId': PLAYFAB_ID, 'appId': APP_ID}])

    async def test_game_server_rejects_unknown_token(self):
        response, _ = await authenticate(self.game_port, real_client_params(token='0' * 32))
        self.assertEqual(response, FAILURE)

    async def test_game_server_answers_create_game_with_response_and_join_only(self):
        # Before the room step the GameServer did not answer 227 at all; it now sends exactly the
        # OperationResponse 227 and the Join event 255, then nothing but pongs.
        reader, writer, _ = await connect_and_authenticate(self.game_port, real_client_params())
        writer.write(frame(2, CREATE_GAME_ON_MASTER) + b'\xf0\x00\x00\x00\x02')
        try:
            self.assertEqual((await read_frame(reader))[:3], b'\xf3\x03\xe3')
            self.assertEqual((await read_frame(reader))[:3], b'\xf3\x04\xff')
            pong = await reader.readexactly(9)
            self.assertEqual((pong[0], pong[5:]), (0xF0, b'\x00\x00\x00\x02'))
        finally:
            writer.close()

    async def game_server_create_game(self):
        reader, writer, _ = await connect_and_authenticate(self.game_port, real_client_params())
        writer.write(frame(2, CREATE_GAME_ON_GAME_SERVER))
        return reader, writer, await read_frame(reader)

    def received(self, key):
        _, params = server.decode_protocol16_operation_request(CREATE_GAME_ON_GAME_SERVER)
        return params[key]

    async def test_game_create_game_response_success_and_order(self):
        reader, writer, response = await self.game_server_create_game()
        writer.close()
        op_code, return_code, debug, params = decode_operation_response(response)
        self.assertEqual((op_code, return_code, debug), (227, 0, None))
        self.assertEqual(list(params), [254, 252, 249, 248])

    async def test_game_create_game_actor_and_actor_list(self):
        reader, writer, response = await self.game_server_create_game()
        writer.close()
        params = decode_operation_response(response)[3]
        self.assertEqual(params[254], 1)
        self.assertEqual(params[252], [1])
        self.assertIn(bytes.fromhex('fe 69 00000001 fc 6e 00000001 00000001'), response)   # int, int[] on the wire

    async def test_game_create_game_echoes_player_and_game_properties(self):
        reader, writer, response = await self.game_server_create_game()
        writer.close()
        params = decode_operation_response(response)[3]
        self.assertEqual(params[249], {1: self.received(249)})
        self.assertEqual(params[248], self.received(248))
        raw = server.decode_protocol16_parameters_raw(CREATE_GAME_ON_GAME_SERVER)[1]
        self.assertIn(b'\xf9\x68\x00\x01\x69\x00\x00\x00\x01' + raw[249], response)   # {(int)1: props verbatim}
        self.assertIn(b'\xf8' + raw[248], response)

    async def test_game_join_event_follows_response(self):
        reader, writer, _ = await self.game_server_create_game()
        code, params = decode_event(await read_frame(reader))
        writer.close()
        self.assertEqual(code, 255)
        self.assertEqual(list(params), [254, 252, 249])
        self.assertEqual((params[254], params[252], params[249]), (1, [1], self.received(249)))

    async def test_game_nothing_else_after_join_event(self):
        reader, writer, _ = await self.game_server_create_game()
        await read_frame(reader)   # Join event
        writer.write(b'\xf0\x00\x00\x00\x03')
        pong = await reader.readexactly(9)
        self.assertEqual((pong[0], pong[5:]), (0xF0, b'\x00\x00\x00\x03'))
        writer.close()

    async def test_master_join_random_returns_no_match(self):
        reader, writer, _ = await connect_and_authenticate(self.port, real_client_params())
        writer.write(frame(2, JOIN_RANDOM_ON_MASTER))
        response = await read_frame(reader)
        writer.close()
        self.assertEqual(response, bytes.fromhex('f3 03 e1 7ff8 2a 0000'))

    async def test_master_create_game_after_no_match_is_answered(self):
        # Normal matchmaking: 225 -> 32760 -> client CreateNewRoom sends the same 227 as the tutorial
        reader, writer, _ = await connect_and_authenticate(self.port, real_client_params())
        writer.write(frame(2, JOIN_RANDOM_ON_MASTER))
        await read_frame(reader)
        writer.write(frame(2, CREATE_GAME_ON_MASTER))
        op_code, return_code, debug, params = decode_operation_response(await read_frame(reader))
        writer.close()
        self.assertEqual((op_code, return_code, debug, sorted(params)), (227, 0, None, [230, 255]))
        self.assertEqual(params[230], GAME_SERVER_ADDRESS)

    async def test_game_server_normal_create_game_joins_room(self):
        # Full 227 of a normal room (t=ts1, MaxPlayers 32, IsOpen true) built from the tutorial capture
        normal = (CREATE_GAME_ON_GAME_SERVER.replace(b'ts0', b'ts1')
                  .replace(b'\x62\xfd\x6f\x00', b'\x62\xfd\x6f\x01').replace(b'\x62\xff\x62\x01', b'\x62\xff\x62\x20'))
        reader, writer, _ = await connect_and_authenticate(self.game_port, real_client_params())
        writer.write(frame(2, normal))
        params = decode_operation_response(await read_frame(reader))[3]
        code, event = decode_event(await read_frame(reader))
        writer.close()
        _, sent = server.decode_protocol16_operation_request(normal)
        self.assertEqual((params[254], params[252], params[249], params[248]), (1, [1], {1: sent[249]}, sent[248]))
        self.assertEqual((params[248]['t'], params[248][253], params[248][255]), ('ts1', True, 32))
        self.assertEqual((code, event[254], event[249]), (255, 1, sent[249]))

    async def joined_game_server(self):
        reader, writer, _ = await self.game_server_create_game()
        await read_frame(reader)   # Join event 255
        return reader, writer

    async def test_quantum_join_answered_with_config_probe(self):
        reader, writer = await self.joined_game_server()
        writer.write(frame(2, RAISE_EVENT_QUANTUM_JOIN))
        payload = await read_frame(reader)
        writer.close()
        self.assertEqual(decode_event(payload), (100, {245: QUANTUM_PROBE}))
        self.assertEqual(payload, b'\xf3\x04\x64\x00\x01\xf5\x78\x00\x00\x00\x0a' + QUANTUM_PROBE)

    async def test_quantum_probe_sent_once(self):
        reader, writer = await self.joined_game_server()
        writer.write(frame(2, RAISE_EVENT_QUANTUM_JOIN))
        await read_frame(reader)
        writer.write(frame(2, RAISE_EVENT_QUANTUM_JOIN) + b'\xf0\x00\x00\x00\x04')
        pong = await reader.readexactly(9)   # second Join: no second probe, only the pong
        writer.close()
        self.assertEqual((pong[0], pong[5:]), (0xF0, b'\x00\x00\x00\x04'))

    async def test_quantum_non_join_and_other_codes_not_answered(self):
        reader, writer = await self.joined_game_server()
        # client answers (SessionConfig/RuntimeConfig), an input event and a PUN RPC event: nothing sent back
        writer.write(frame(2, raise_event(100, bytes.fromhex('03 00')))
                     + frame(2, raise_event(102, b'\x01\x02')) + frame(2, raise_event(200, b'\x00'))
                     + b'\xf0\x00\x00\x00\x05')
        pong = await reader.readexactly(9)
        writer.close()
        self.assertEqual((pong[0], pong[5:]), (0xF0, b'\x00\x00\x00\x05'))

    async def probed_game_server(self):
        reader, writer = await self.joined_game_server()
        writer.write(frame(2, RAISE_EVENT_QUANTUM_JOIN))
        await read_frame(reader)   # probe
        return reader, writer

    async def test_simulation_start_after_client_configs(self):
        reader, writer = await self.probed_game_server()
        writer.write(frame(2, raise_event(100, CLIENT_CONFIG_REPLY)))
        code, params = decode_event(await read_frame(reader))
        writer.close()
        self.assertEqual((code, list(params)), (100, [245]))
        self.assertEqual(len(params[245]), 1800)
        self.assertEqual(hashlib.sha256(params[245]).hexdigest(), SIMULATION_START_SHA256)

    async def test_simulation_start_waits_for_both_configs(self):
        # same configs in two events (SessionConfig, then RuntimeConfig): SimulationStart only after the second
        w = quantum.BitWriter()   # SessionConfig message alone: bits 0-656 of the real answer
        w.write(quantum.read_raw_bits(CLIENT_CONFIG_REPLY, 0, 657), 657)
        runtime = quantum.BitWriter()
        runtime.write(quantum.MSG_RUNTIME_CONFIG, 8)
        runtime.write_bool(False)
        runtime.write_byte_array(RUNTIME_CONFIG)
        reader, writer = await self.probed_game_server()
        writer.write(frame(2, raise_event(100, w.to_bytes())) + b'\xf0\x00\x00\x00\x06')
        pong = await reader.readexactly(9)
        self.assertEqual((pong[0], pong[5:]), (0xF0, b'\x00\x00\x00\x06'))
        writer.write(frame(2, raise_event(100, runtime.to_bytes())))
        code, params = decode_event(await read_frame(reader))
        writer.close()
        self.assertEqual(hashlib.sha256(params[245]).hexdigest(), SIMULATION_START_SHA256)

    async def test_simulation_start_sent_once_and_102_not_answered(self):
        reader, writer = await self.probed_game_server()
        writer.write(frame(2, raise_event(100, CLIENT_CONFIG_REPLY)))
        await read_frame(reader)   # SimulationStart
        writer.write(frame(2, raise_event(100, CLIENT_CONFIG_REPLY)) + frame(2, raise_event(102, b'\x01\x02'))
                     + b'\xf0\x00\x00\x00\x07')
        pong = await reader.readexactly(9)
        writer.close()
        self.assertEqual((pong[0], pong[5:]), (0xF0, b'\x00\x00\x00\x07'))

    async def simulation_started_game_server(self):
        reader, writer = await self.probed_game_server()
        writer.write(frame(2, raise_event(100, CLIENT_CONFIG_REPLY)))
        await read_frame(reader)   # SimulationStart
        return reader, writer

    async def test_client_input_relayed_as_verified_input(self):
        reader, writer = await self.simulation_started_game_server()
        writer.write(frame(2, raise_event(102, bytes.fromhex('001e0000000900000000000400'))))
        code, params = decode_event(await read_frame(reader))
        writer.close()
        self.assertEqual((code, list(params)), (102, [245]))
        decoded = quantum.decode_server_inputs(params[245])
        self.assertEqual([(t['Tick'], t['Inputs']) for t in decoded['Ticks']],
                         [(30, {0: {'Data': bytes(4), 'Rpc': None, 'Flags': 1}})])
        self.assertEqual(len(params[245]), 33)

    async def test_each_tick_relayed_once(self):
        reader, writer = await self.simulation_started_game_server()
        writer.write(frame(2, raise_event(102, bytes.fromhex('001e0000000900000000000400')))
                     + frame(2, raise_event(102, bytes.fromhex('001e00000009000000000004007c0000002400000000001000')))
                     + b'\xf0\x00\x00\x00\x08')
        ticks = [quantum.decode_server_inputs(decode_event(await read_frame(reader))[1][245])['Ticks'][0]['Tick']
                 for _ in range(2)]
        pong = await reader.readexactly(9)   # tick 30 repeated in the second event: not relayed again
        writer.close()
        self.assertEqual((ticks, pong[0], pong[5:]), ([30, 31], 0xF0, b'\x00\x00\x00\x08'))

    async def test_input_before_simulation_start_not_relayed(self):
        reader, writer = await self.probed_game_server()
        writer.write(frame(2, raise_event(102, bytes.fromhex('001e0000000900000000000400'))) + b'\xf0\x00\x00\x00\x09')
        pong = await reader.readexactly(9)
        writer.close()
        self.assertEqual((pong[0], pong[5:]), (0xF0, b'\x00\x00\x00\x09'))

    def test_parse_auth_get_parameters(self):
        self.assertEqual(server.parse_auth_get_parameters(f'username={PLAYFAB_ID}&token={TOKEN}'), (PLAYFAB_ID, TOKEN))
        self.assertEqual(server.parse_auth_get_parameters(''), (None, None))


if __name__ == '__main__':
    unittest.main()
