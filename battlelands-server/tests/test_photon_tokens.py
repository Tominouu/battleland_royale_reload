"""Photon custom-auth token binding and POST /internal/photon/validate.

Run from battlelands-server/: venv/bin/python -m unittest discover tests
Handlers are called directly (not through the PlayFab router) so logs/requests.jsonl is not touched.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from playfab import auth, photon_tokens  # noqa: E402

APP_ID = "774b10b9-5bfb-48a7-9971-55300fc0d4bd"
PLAYFAB_ID = "95B0723D9D844E0B"
SESSION = PLAYFAB_ID + "-TEST-SESSION"
HOST = {"REMOTE_ADDR": "127.0.0.1"}


class PhotonTokenTests(unittest.TestCase):
    def setUp(self):
        photon_tokens._tokens.clear()
        auth._sessions[SESSION] = PLAYFAB_ID
        self.client = app.test_client()

    def tearDown(self):
        auth._sessions.pop(SESSION, None)
        photon_tokens._tokens.clear()

    def issue(self, app_id=APP_ID):
        with app.test_request_context():
            response = auth.get_photon_authentication_token({"PhotonApplicationId": app_id}, SESSION)
        return response.get_json()["data"]["PhotonCustomAuthenticationToken"]

    def validate(self, token, playfab_id=PLAYFAB_ID, app_id=APP_ID, caller=HOST):
        return self.client.post("/internal/photon/validate", environ_base=caller,
                                json={"token": token, "playFabId": playfab_id, "appId": app_id})

    def test_issued_token_is_stored_with_binding(self):
        token = self.issue()
        record = photon_tokens._tokens[token]
        self.assertEqual(len(token), 32)
        self.assertEqual((record["playfab_id"], record["app_id"]), (PLAYFAB_ID, APP_ID))
        self.assertEqual(record["expires_at"] - record["created_at"], photon_tokens.TOKEN_TTL_SECONDS)

    def test_a_valid_token(self):
        response = self.validate(self.issue())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"valid": True, "playFabId": PLAYFAB_ID})

    def test_b_unknown_token(self):
        self.issue()
        self.assertEqual(self.validate("0" * 32).get_json(), {"valid": False, "reason": "unknown token"})

    def test_c_wrong_playfab_id(self):
        result = self.validate(self.issue(), playfab_id="0000000000000000").get_json()
        self.assertEqual(result, {"valid": False, "reason": "PlayFabId mismatch"})

    def test_d_wrong_app_id(self):
        result = self.validate(self.issue(), app_id="2fd21053-1cdf-4067-887c-b83edd1a1af4").get_json()
        self.assertEqual(result, {"valid": False, "reason": "AppId mismatch"})

    def test_e_expired_token(self):
        token = self.issue()
        photon_tokens._tokens[token]["expires_at"] -= photon_tokens.TOKEN_TTL_SECONDS + 1
        self.assertEqual(self.validate(token).get_json(), {"valid": False, "reason": "expired token"})
        self.assertNotIn(token, photon_tokens._tokens)

    def test_f_replay_allowed_until_expiry(self):
        token = self.issue()
        for _ in range(3):
            self.assertTrue(self.validate(token).get_json()["valid"])
        photon_tokens._tokens[token]["expires_at"] = 0
        self.assertFalse(self.validate(token).get_json()["valid"])

    def test_missing_fields(self):
        self.issue()
        response = self.client.post("/internal/photon/validate", environ_base=HOST, json={})
        self.assertEqual(response.get_json(), {"valid": False, "reason": "unknown token"})

    def test_container_caller_forbidden(self):
        response = self.validate(self.issue(), caller={"REMOTE_ADDR": "192.168.240.112"})
        self.assertEqual(response.status_code, 403)

    def test_no_session_no_token(self):
        with app.test_request_context():
            response = auth.get_photon_authentication_token({"PhotonApplicationId": APP_ID}, "bad-ticket")
        self.assertEqual(response.get_json()["code"], 401)
        self.assertEqual(photon_tokens._tokens, {})


if __name__ == "__main__":
    unittest.main()
