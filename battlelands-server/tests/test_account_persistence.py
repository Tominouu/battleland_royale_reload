"""Login keys and display names survive a server restart (storage/players/accounts.json, profile.json).

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

INFO = {"GetUserAccountInfo": True}


def restart():
    """What a gunicorn reload loses: every in-memory table."""
    auth._players.clear()
    auth._display_names.clear()
    auth._sessions.clear()


class AccountPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.storage, self.saved_dir = tempfile.mkdtemp(), player_data.DATA_DIR
        player_data.DATA_DIR = self.storage
        self.device = uuid.uuid4().hex

    def tearDown(self):
        player_data.DATA_DIR = self.saved_dir
        shutil.rmtree(self.storage)
        restart()

    def login(self, device=None):
        with app.test_request_context():
            return auth.login_with_android_device_id(
                {"AndroidDeviceId": device or self.device, "CreateAccount": True, "InfoRequestParameters": INFO},
                None).get_json()["data"]

    def test_same_account_after_restart(self):
        first = self.login()
        restart()
        second = self.login()
        self.assertEqual(second["PlayFabId"], first["PlayFabId"])
        self.assertEqual((first["NewlyCreated"], second["NewlyCreated"]), (True, False))

    def test_display_name_after_restart(self):
        ticket = self.login()["SessionTicket"]
        with app.test_request_context():
            auth.update_user_title_display_name({"DisplayName": "Tom#"}, ticket)
        restart()
        self.assertEqual(self.login()["InfoResultPayload"]["AccountInfo"]["TitleInfo"]["DisplayName"], "Tom#")

    def test_other_device_gets_other_account(self):
        first = self.login()
        restart()
        self.assertNotEqual(self.login(uuid.uuid4().hex)["PlayFabId"], first["PlayFabId"])

    def test_linked_device_after_restart(self):
        first = self.login()
        other_device = uuid.uuid4().hex
        with app.test_request_context():
            auth.link_android_device_id({"AndroidDeviceId": other_device}, first["SessionTicket"])
        restart()
        self.assertEqual(self.login(other_device)["PlayFabId"], first["PlayFabId"])


if __name__ == "__main__":
    unittest.main()
