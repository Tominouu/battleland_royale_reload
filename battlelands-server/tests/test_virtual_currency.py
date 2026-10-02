"""Persistent virtual currency wallet (GE, BB, BT, DT, XP), the same in login UserVirtualCurrency,
initializeDataS5 VirtualCurrency and GetUserInventory VirtualCurrency.

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
from playfab import auth, cloudscript, data  # noqa: E402
from storage import player_data  # noqa: E402

ZERO = {"GE": 0, "BB": 0, "BT": 0, "DT": 0, "XP": 0}
WALLET = {"GE": 100, "BB": 50, "BT": 3, "DT": 7, "XP": 42}
LOGIN_INFO = {"GetUserVirtualCurrency": True, "GetPlayerStatistics": True}


def restart():
    """What a gunicorn reload loses: every in-memory table."""
    auth._players.clear()
    auth._display_names.clear()
    auth._sessions.clear()


class VirtualCurrencyTests(unittest.TestCase):
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

    def initialize_data(self, ticket):
        body = {"FunctionName": "initializeDataS5", "FunctionParameter": {"SessionId": uuid.uuid4().hex}}
        with app.test_request_context():
            return cloudscript.execute_cloud_script(body, ticket).get_json()["data"]["FunctionResult"]

    def user_inventory(self, ticket):
        with app.test_request_context():
            return data.get_user_inventory({}, ticket).get_json()["data"]

    def test_new_player_has_zero_balances(self):
        login = self.login()
        self.assertEqual(login["InfoResultPayload"]["UserVirtualCurrency"], ZERO)
        self.assertEqual(player_data.get_virtual_currency(login["PlayFabId"]), ZERO)

    def test_set_then_get(self):
        playfab_id = self.login()["PlayFabId"]
        player_data.set_virtual_currency(playfab_id, WALLET)
        self.assertEqual(player_data.get_virtual_currency(playfab_id), WALLET)

    def test_partial_set_keeps_other_codes(self):
        playfab_id = self.login()["PlayFabId"]
        player_data.set_virtual_currency(playfab_id, WALLET)
        player_data.set_virtual_currency(playfab_id, {"GE": 5})
        self.assertEqual(player_data.get_virtual_currency(playfab_id), dict(WALLET, GE=5))

    def test_invalid_values_rejected(self):
        playfab_id = self.login()["PlayFabId"]
        for bad in ({"GE": -1}, {"GE": 1.5}, {"GE": "10"}, {"GE": True}, {"ZZ": 1}):
            with self.assertRaises(ValueError):
                player_data.set_virtual_currency(playfab_id, bad)
        self.assertEqual(player_data.get_virtual_currency(playfab_id), ZERO)

    def test_login_returns_wallet(self):
        playfab_id = self.login()["PlayFabId"]
        player_data.set_virtual_currency(playfab_id, WALLET)
        self.assertEqual(self.login()["InfoResultPayload"]["UserVirtualCurrency"], WALLET)

    def test_initialize_data_returns_wallet(self):
        login = self.login()
        player_data.set_virtual_currency(login["PlayFabId"], WALLET)
        self.assertEqual(self.initialize_data(login["SessionTicket"])["VirtualCurrency"], WALLET)

    def test_get_user_inventory_returns_wallet(self):
        login = self.login()
        player_data.set_virtual_currency(login["PlayFabId"], WALLET)
        inventory = self.user_inventory(login["SessionTicket"])
        self.assertEqual(inventory["VirtualCurrency"], WALLET)
        self.assertEqual(inventory["Inventory"], [])

    def test_wallet_persists_after_restart(self):
        playfab_id = self.login()["PlayFabId"]
        player_data.set_virtual_currency(playfab_id, WALLET)
        restart()
        login = self.login()
        self.assertEqual(login["PlayFabId"], playfab_id)
        self.assertEqual(login["InfoResultPayload"]["UserVirtualCurrency"], WALLET)
        self.assertEqual(self.initialize_data(login["SessionTicket"])["VirtualCurrency"], WALLET)
        self.assertEqual(self.user_inventory(login["SessionTicket"])["VirtualCurrency"], WALLET)

    def test_existing_player_without_wallet_file_gets_zeros(self):
        login = self.login()
        self.assertFalse(os.path.exists(os.path.join(self.storage, "players", "virtual_currency.json")))
        self.assertEqual(self.initialize_data(login["SessionTicket"])["VirtualCurrency"], ZERO)
        self.assertEqual(self.user_inventory(login["SessionTicket"])["VirtualCurrency"], ZERO)

    def test_players_are_independent(self):
        first, other = self.login()["PlayFabId"], self.login(uuid.uuid4().hex)["PlayFabId"]
        player_data.set_virtual_currency(first, WALLET)
        self.assertEqual(player_data.get_virtual_currency(other), ZERO)

    def test_trophies_independent_of_wallet(self):
        login = self.login()
        player_data.set_virtual_currency(login["PlayFabId"], WALLET)
        body = {"FunctionName": "pingNodesT", "FunctionParameter": {"P1": 1}}
        with app.test_request_context():
            result = cloudscript.execute_cloud_script(body, login["SessionTicket"]).get_json()["data"]["FunctionResult"]
        self.assertEqual(result, {"R1": 0, "R2": 10, "R3": 0})
        self.assertEqual(player_data.get_virtual_currency(login["PlayFabId"]), WALLET)
        statistics = self.login()["InfoResultPayload"]["PlayerStatistics"]
        self.assertIn({"StatisticName": "Trophies_Season14", "Value": 10}, statistics)

    def test_wallet_not_in_read_only_data(self):
        playfab_id = self.login()["PlayFabId"]
        player_data.set_virtual_currency(playfab_id, WALLET)
        self.assertEqual(player_data.get_read_only_data(playfab_id), {})


if __name__ == "__main__":
    unittest.main()
