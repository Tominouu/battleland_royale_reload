"""CloudScript purchaseChest: price from our catalog, provisional gem rewards (RewardType 7), wallet debit + credit.

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

CODES = {"GE", "BB", "BT", "DT", "XP"}
OTHERS = {"BB": 50, "BT": 3, "DT": 7, "XP": 42}


def restart():
    auth._players.clear()
    auth._display_names.clear()
    auth._sessions.clear()


class PurchaseChestTests(unittest.TestCase):
    def setUp(self):
        self.storage, self.saved_dir = tempfile.mkdtemp(), player_data.DATA_DIR
        player_data.DATA_DIR = self.storage
        self.device = uuid.uuid4().hex
        login = self.login()
        self.playfab_id, self.ticket = login["PlayFabId"], login["SessionTicket"]

    def tearDown(self):
        player_data.DATA_DIR = self.saved_dir
        shutil.rmtree(self.storage)
        restart()

    def login(self):
        with app.test_request_context():
            return auth.login_with_android_device_id(
                {"AndroidDeviceId": self.device, "CreateAccount": True,
                 "InfoRequestParameters": {"GetUserVirtualCurrency": True, "GetPlayerStatistics": True}},
                None).get_json()["data"]

    def purchase(self, chest, price_gems, discount=False):
        # Same parameters as PurchaseChestParams sent by UIBoxShop
        body = {"FunctionName": "purchaseChest", "FunctionParameter": {
            "ChestItemId": chest, "PriceGems": price_gems, "Discount": discount, "SubstituteMaxLevelCards": True}}
        with app.test_request_context():
            return cloudscript.execute_cloud_script(body, self.ticket).get_json()["data"]

    def wallet(self, gems):
        player_data.set_virtual_currency(self.playfab_id, dict(OTHERS, GE=gems))

    def assert_bought(self, chest, before, price, reward):
        self.wallet(before)
        data = self.purchase(chest, price)
        self.assertNotIn("Error", data)
        result = data["FunctionResult"]
        self.assertEqual(result["VirtualCurrency"], dict(OTHERS, GE=before - price + reward))
        self.assertEqual(result["ChestRewards"], [{"Type": 7, "Amount": reward, "Parameter": ""}])
        self.assertEqual(player_data.get_virtual_currency(self.playfab_id), dict(OTHERS, GE=before - price + reward))
        return result

    def assert_rejected(self, data, error, gems):
        self.assertEqual(data["Error"]["Error"], error)
        self.assertNotIn("FunctionResult", data)
        self.assertEqual(player_data.get_virtual_currency(self.playfab_id), dict(OTHERS, GE=gems))

    def test_battle_chest_with_exactly_the_price(self):
        self.assert_bought("ChestBattle", 100, 100, 150)

    def test_battle_chest_with_more_gems(self):
        self.assert_bought("ChestBattle", 500, 100, 150)

    def test_premium_chest(self):
        self.assert_bought("ChestBattlePremium", 250, 250, 400)

    def test_lucky_chest(self):
        self.assert_bought("ChestLucky", 50, 50, 75)

    def test_client_price_is_ignored(self):
        self.wallet(100)
        data = self.purchase("ChestBattle", 1)
        self.assertEqual(data["FunctionResult"]["VirtualCurrency"]["GE"], 150)   # 100 - 100 + 150, not 100 - 1 + 150

    def test_insufficient_gems(self):
        self.wallet(99)
        self.assert_rejected(self.purchase("ChestBattle", 100), "InsufficientFunds", 99)

    def test_unknown_chest(self):
        self.wallet(1000)
        self.assert_rejected(self.purchase("ChestGolden", 100), "InvalidItem", 1000)
        self.assert_rejected(self.purchase("MrBunny", 0), "InvalidItem", 1000)   # catalog item, not a chest

    def test_discount_rejected(self):
        self.wallet(1000)
        self.assert_rejected(self.purchase("ChestBattle", 50, discount=True), "InvalidParams", 1000)

    def test_virtual_currency_has_the_five_codes(self):
        result = self.assert_bought("ChestLucky", 60, 50, 75)
        self.assertEqual(set(result["VirtualCurrency"]), CODES)

    def test_no_skin_inventory_in_response(self):
        result = self.assert_bought("ChestBattle", 100, 100, 150)
        self.assertEqual(set(result), {"VirtualCurrency", "ChestRewards"})

    def test_trophies_unchanged(self):
        player_data.set_statistic(self.playfab_id, "Trophies_Season14", 18)
        self.assert_bought("ChestBattle", 100, 100, 150)
        self.purchase("ChestBattle", 100)   # second one rejected (50 GE left)
        self.assertEqual(player_data.get_statistics(self.playfab_id), {"Trophies_Season14": 18})

    def test_balance_persists_after_restart(self):
        self.assert_bought("ChestBattle", 100, 100, 150)
        restart()
        self.assertEqual(self.login()["InfoResultPayload"]["UserVirtualCurrency"], dict(OTHERS, GE=150))

    def test_catalog_served_unchanged(self):
        body = {"FunctionName": "initializeDataS5", "FunctionParameter": {"SessionId": "s"}}
        with app.test_request_context():
            result = cloudscript.execute_cloud_script(body, self.ticket).get_json()["data"]["FunctionResult"]
        chests = {i["ItemId"]: i["VirtualCurrencyPrices"] for i in result["Catalogs"]["SeasonItems_14"]
                  if i["ItemClass"] == "Chest"}
        self.assertEqual(chests, {"ChestBattle": {"GE": 100}, "ChestBattlePremium": {"GE": 250},
                                  "ChestLucky": {"GE": 50}})
        self.assertEqual(len(result["Catalogs"]["SeasonItems_14"]), 13)


if __name__ == "__main__":
    unittest.main()
