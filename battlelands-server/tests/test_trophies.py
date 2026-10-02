"""Persistent trophies: PlayerStatistics Trophies_Season14 at login, updated by pingNodesT (R1 before, R2 after).

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

# Real FunctionParameter (build/twomatch-test), position P1 replaced per test
PING_NODES_PARAMS = {"P1": 8, "P2": 2, "P3": "tutorial-bed50b93", "P4": 1, "P5": 0, "P6": False, "P7": "840",
                     "P8": ["D1_1"], "P9": [], "P10": 8, "P11": 14, "P12": 0, "P13": 1,
                     "P14": "726feec9-2b04-495b-8c9b-290247f8b056", "P15": 269, "P16": "", "P17": False,
                     "P18": 0, "P19": 0}
LOGIN_INFO = {"GetPlayerStatistics": True}


def restart():
    """What a gunicorn reload loses: every in-memory table."""
    auth._players.clear()
    auth._display_names.clear()
    auth._sessions.clear()


class TrophiesTests(unittest.TestCase):
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
                {"AndroidDeviceId": device or self.device, "CreateAccount": True, "InfoRequestParameters": LOGIN_INFO},
                None).get_json()["data"]

    def login_trophies(self, device=None):
        statistics = self.login(device)["InfoResultPayload"]["PlayerStatistics"]
        return {s["StatisticName"]: s["Value"] for s in statistics}

    def ping_nodes_t(self, ticket, position):
        body = {"FunctionName": "pingNodesT", "FunctionParameter": dict(PING_NODES_PARAMS, P1=position),
                "GeneratePlayStreamEvent": True, "RevisionSelection": None, "SpecificRevision": None,
                "AuthenticationContext": None}
        with app.test_request_context():
            data = cloudscript.execute_cloud_script(body, ticket).get_json()["data"]
        self.assertNotIn("Error", data)
        return data["FunctionResult"]

    def test_new_player_has_zero_trophies_at_login(self):
        self.assertEqual(self.login_trophies(), {"Season": 14, "Trophies_Season14": 0})

    def test_first_place_gives_10(self):
        ticket = self.login()["SessionTicket"]
        self.assertEqual(self.ping_nodes_t(ticket, 1), {"R1": 0, "R2": 10, "R3": 0})

    def test_second_match_starts_from_previous_value(self):
        ticket = self.login()["SessionTicket"]
        self.ping_nodes_t(ticket, 1)
        self.assertEqual(self.ping_nodes_t(ticket, 3), {"R1": 10, "R2": 16, "R3": 0})

    def test_gain_per_position(self):
        ticket = self.login()["SessionTicket"]
        total = 0
        for position, gain in ((1, 10), (2, 8), (3, 6), (4, 4), (5, 2), (6, 0), (32, 0)):
            self.assertEqual(self.ping_nodes_t(ticket, position), {"R1": total, "R2": total + gain, "R3": 0})
            total += gain

    def test_position_8_leaves_trophies_unchanged(self):
        ticket = self.login()["SessionTicket"]
        self.ping_nodes_t(ticket, 2)
        self.assertEqual(self.ping_nodes_t(ticket, 8), {"R1": 8, "R2": 8, "R3": 0})
        self.assertEqual(self.login_trophies()["Trophies_Season14"], 8)

    def test_missing_or_invalid_position_gives_nothing(self):
        ticket = self.login()["SessionTicket"]
        for position in (None, "1", True, 0, -1):
            self.assertEqual(self.ping_nodes_t(ticket, position), {"R1": 0, "R2": 0, "R3": 0})

    def test_never_negative(self):
        ticket = self.login()["SessionTicket"]
        player_data.set_statistic(self.login()["PlayFabId"], "Trophies_Season14", -5)
        self.assertEqual(self.ping_nodes_t(ticket, 8)["R2"], 0)

    def test_trophies_persist_after_restart(self):
        ticket = self.login()["SessionTicket"]
        self.ping_nodes_t(ticket, 1)
        restart()
        # new session after the restart, same account: pingNodesT continues from the stored value
        ticket = self.login()["SessionTicket"]
        self.assertEqual(self.ping_nodes_t(ticket, 4), {"R1": 10, "R2": 14, "R3": 0})

    def test_login_after_restart_returns_stored_trophies(self):
        ticket = self.login()["SessionTicket"]
        self.ping_nodes_t(ticket, 1)
        self.ping_nodes_t(ticket, 2)
        restart()
        self.assertEqual(self.login_trophies(), {"Season": 14, "Trophies_Season14": 18})

    def test_players_are_independent(self):
        other = uuid.uuid4().hex
        ticket, other_ticket = self.login()["SessionTicket"], self.login(other)["SessionTicket"]
        self.ping_nodes_t(ticket, 1)
        self.assertEqual(self.ping_nodes_t(other_ticket, 5), {"R1": 0, "R2": 2, "R3": 0})
        restart()
        self.assertEqual(self.login_trophies()["Trophies_Season14"], 10)
        self.assertEqual(self.login_trophies(other)["Trophies_Season14"], 2)

    def test_trophies_not_exposed_as_read_only_data(self):
        ticket = self.login()["SessionTicket"]
        self.ping_nodes_t(ticket, 1)
        self.assertNotIn("Trophies_Season14", player_data.get_read_only_data(self.login()["PlayFabId"]))


if __name__ == "__main__":
    unittest.main()
