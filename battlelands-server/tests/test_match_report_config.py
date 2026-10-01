"""TitleData MatchReportConfig_14 as read by MatchReportRunner.OnMatchEnded after a match.

Run from battlelands-server/: venv/bin/python -m unittest discover tests
"""
import json
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

# Bootstrap test values, not the historical configuration
EXPECTED = {"DailyRewardCount": 0, "BattlebucksDistribution": [0],
            "Rewards": [{"TypeString": "AddToGems", "Amount": 0, "Parameter": ""}]}


class MatchReportConfigTests(unittest.TestCase):
    def setUp(self):
        self.storage, self.saved_dir = tempfile.mkdtemp(), player_data.DATA_DIR
        player_data.DATA_DIR = self.storage

    def tearDown(self):
        player_data.DATA_DIR = self.saved_dir
        shutil.rmtree(self.storage)

    def title_data(self):
        with app.test_request_context():
            return auth.login_with_android_device_id(
                {"AndroidDeviceId": uuid.uuid4().hex, "CreateAccount": True,
                 "InfoRequestParameters": {"GetTitleData": True}}, None).get_json()["data"]["InfoResultPayload"]["TitleData"]

    def test_served_as_json_string(self):
        value = self.title_data()["MatchReportConfig_14"]
        self.assertIsInstance(value, str)
        self.assertEqual(json.loads(value), EXPECTED)

    def test_lists_read_by_get_random_are_not_empty(self):
        config = json.loads(self.title_data()["MatchReportConfig_14"])
        self.assertGreater(len(config["BattlebucksDistribution"]), 0)
        self.assertGreater(len(config["Rewards"]), 0)
        self.assertIsNotNone(config["Rewards"][0])


if __name__ == "__main__":
    unittest.main()
