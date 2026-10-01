"""CloudScript saveMatchCount, sent by PlayFabRunner.HandleIncompleteMatches during login.

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
from playfab import auth, cloudscript  # noqa: E402
from storage import player_data  # noqa: E402


class SaveMatchCountTests(unittest.TestCase):
    def setUp(self):
        self.storage, self.saved_dir = tempfile.mkdtemp(), player_data.DATA_DIR
        player_data.DATA_DIR = self.storage
        with app.test_request_context():
            login = auth.login_with_android_device_id(
                {"AndroidDeviceId": uuid.uuid4().hex, "CreateAccount": True}, None).get_json()["data"]
        self.ticket = login["SessionTicket"]

    def tearDown(self):
        player_data.DATA_DIR = self.saved_dir
        shutil.rmtree(self.storage)

    def save_match_count(self, match_count):
        # Same body as the real client (build/continue-test/logs/backend-requests.jsonl)
        body = {"FunctionName": "saveMatchCount", "FunctionParameter": {"MatchCount": match_count},
                "GeneratePlayStreamEvent": True, "RevisionSelection": None, "SpecificRevision": None,
                "AuthenticationContext": None}
        with app.test_request_context():
            response = cloudscript.execute_cloud_script(body, self.ticket)
            return response.status_code, response.get_json()

    def test_match_count_1_succeeds_without_error(self):
        status, body = self.save_match_count(1)
        self.assertEqual((status, body["code"], body["status"]), (200, 200, "OK"))
        self.assertNotIn("Error", body["data"])
        self.assertEqual(body["data"], {"FunctionName": "saveMatchCount", "FunctionResult": None})

    def test_other_match_count_accepted(self):
        status, body = self.save_match_count(7)
        self.assertEqual((status, body["code"]), (200, 200))
        self.assertEqual(body["data"], {"FunctionName": "saveMatchCount", "FunctionResult": None})


if __name__ == "__main__":
    unittest.main()
