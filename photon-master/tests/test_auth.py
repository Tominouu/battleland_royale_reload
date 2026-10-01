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
        game = server.PhotonTCPServer('127.0.0.1', 0, validator, server.ROLE_GAME)
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

    async def test_game_server_does_not_answer_create_game(self):
        reader, writer, _ = await connect_and_authenticate(self.game_port, real_client_params())
        writer.write(frame(2, CREATE_GAME_ON_MASTER) + b'\xf0\x00\x00\x00\x02')
        pong = await reader.readexactly(9)   # the next bytes are the pong, not an OperationResponse
        self.assertEqual((pong[0], pong[5:]), (0xF0, b'\x00\x00\x00\x02'))
        writer.close()

    def test_parse_auth_get_parameters(self):
        self.assertEqual(server.parse_auth_get_parameters(f'username={PLAYFAB_ID}&token={TOKEN}'), (PLAYFAB_ID, TOKEN))
        self.assertEqual(server.parse_auth_get_parameters(''), (None, None))


if __name__ == '__main__':
    unittest.main()
