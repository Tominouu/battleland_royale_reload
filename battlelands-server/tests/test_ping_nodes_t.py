"""CloudScript pingNodesT, sent by PlayFabRunner.MatchEnded after CONTINUE on the end-of-match screen.

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

# FunctionParameter of the real request (build/matchreport-test/logs/pingNodesT-request.json)
PING_NODES_PARAMS = {"P1": 8, "P2": 2, "P3": "tutorial-b5ac2895", "P4": 1, "P5": 0, "P6": False, "P7": "840",
                     "P8": ["D1_1"], "P9": [], "P10": 8, "P11": 14, "P12": 0, "P13": 1,
                     "P14": "38475d16-8a74-4022-9ddd-5697e441436a", "P15": 269, "P16": "", "P17": False,
                     "P18": 0, "P19": 0}


class PingNodesTTests(unittest.TestCase):
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

    def ping_nodes_t(self):
        body = {"FunctionName": "pingNodesT", "FunctionParameter": PING_NODES_PARAMS, "GeneratePlayStreamEvent": True,
                "RevisionSelection": None, "SpecificRevision": None, "AuthenticationContext": None}
        with app.test_request_context():
            response = cloudscript.execute_cloud_script(body, self.ticket)
            return response.status_code, response.get_json()

    def test_success_without_error(self):
        status, body = self.ping_nodes_t()
        self.assertEqual((status, body["code"], body["status"]), (200, 200, "OK"))
        self.assertEqual(body["data"]["FunctionName"], "pingNodesT")
        self.assertNotIn("Error", body["data"])

    def test_function_result_is_empty_object_not_null(self):
        # <MatchEnded>b__77_1 dereferences FunctionResult unchecked: null would throw in the client
        _, body = self.ping_nodes_t()
        self.assertIn("FunctionResult", body["data"])
        self.assertIsNotNone(body["data"]["FunctionResult"])
        self.assertEqual(body["data"]["FunctionResult"], {})


if __name__ == "__main__":
    unittest.main()
