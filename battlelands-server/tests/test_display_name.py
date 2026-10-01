"""UpdateUserTitleDisplayName and the DisplayName returned by the next login.

Run from battlelands-server/: venv/bin/python -m unittest discover tests
"""
import os
import shutil
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from playfab import auth  # noqa: E402
from storage import player_data  # noqa: E402

# InfoRequestParameters flags the real client sends with LoginWithAndroidDeviceID
INFO = {"GetUserAccountInfo": True, "GetTitleData": True, "GetUserReadOnlyData": True, "GetPlayerStatistics": True}


class DisplayNameTests(unittest.TestCase):
    def setUp(self):
        self.device = uuid.uuid4().hex
        # login reads storage/players/<PlayFabId>; keep tests out of the real player storage
        self.storage, self.saved_dir = tempfile.mkdtemp(), player_data.DATA_DIR
        player_data.DATA_DIR = self.storage

    def tearDown(self):
        player_data.DATA_DIR = self.saved_dir
        shutil.rmtree(self.storage)

    def call(self, handler, body, ticket=None):
        with app.test_request_context():
            return handler(body, ticket).get_json()

    def login(self):
        result = self.call(auth.login_with_android_device_id,
                           {"AndroidDeviceId": self.device, "CreateAccount": True, "InfoRequestParameters": INFO})
        return result["data"]

    def update(self, ticket, name):
        return self.call(auth.update_user_title_display_name, {"DisplayName": name, "AuthenticationContext": None}, ticket)

    def test_a_new_player_has_no_display_name(self):
        data = self.login()
        self.assertIsNone(data["InfoResultPayload"]["AccountInfo"]["TitleInfo"]["DisplayName"])

    def test_b_update_returns_200_and_the_name(self):
        result = self.update(self.login()["SessionTicket"], "Tom#")
        self.assertEqual(result, {"code": 200, "status": "OK", "data": {"DisplayName": "Tom#"}})

    def test_c_next_login_returns_the_name(self):
        first = self.login()
        self.update(first["SessionTicket"], "Tom#")
        second = self.login()
        self.assertEqual(second["PlayFabId"], first["PlayFabId"])
        self.assertEqual(second["InfoResultPayload"]["AccountInfo"]["TitleInfo"]["DisplayName"], "Tom#")

    def test_d_same_name_twice_succeeds(self):
        ticket = self.login()["SessionTicket"]
        self.assertEqual(self.update(ticket, "Tom#")["code"], 200)
        self.assertEqual(self.update(ticket, "Tom#")["data"], {"DisplayName": "Tom#"})

    def test_e_other_valid_name_replaces_it(self):
        ticket = self.login()["SessionTicket"]
        self.update(ticket, "Tom#")
        self.assertEqual(self.update(ticket, "Ruby#")["data"], {"DisplayName": "Ruby#"})
        self.assertEqual(self.login()["InfoResultPayload"]["AccountInfo"]["TitleInfo"]["DisplayName"], "Ruby#")

    def test_f_invalid_payload(self):
        ticket = self.login()["SessionTicket"]
        for body in ({}, {"DisplayName": None}, {"DisplayName": 42}, {"DisplayName": "T#"}, {"DisplayName": "x" * 26}):
            with self.subTest(body=body):
                with app.test_request_context():
                    result = auth.update_user_title_display_name(body, ticket).get_json()
                self.assertEqual((result["code"], result["error"], result["errorCode"]), (400, "InvalidParams", 1000))
        self.assertIsNone(self.login()["InfoResultPayload"]["AccountInfo"]["TitleInfo"]["DisplayName"])

    def test_without_session(self):
        result = self.update("bad-ticket", "Tom#")
        self.assertEqual(result["code"], 401)


if __name__ == "__main__":
    unittest.main()
