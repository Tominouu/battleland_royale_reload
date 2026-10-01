"""CloudScript saveS5 and the player data returned by the next login.

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
from playfab import auth, cloudscript  # noqa: E402
from storage import player_data  # noqa: E402

INFO = {"GetUserAccountInfo": True, "GetTitleData": True, "GetUserReadOnlyData": True, "GetPlayerStatistics": True}
# GameSettings.MinimumAcceptedVersion: accepting the Terms copies it into B_ACV, observed as 1
MINIMUM_ACCEPTED_VERSION = 1
BASE = json.dumps({"B_PI": "9d283dab-bcff-402a-a17b-dde3a3e20000", "B_AV": "2.9.6", "B_SFV": 8, "B_ACV": 1,
                   "B_LSB": "battletag_set"})
GAME = json.dumps({"T_S": "SetBattleTag", "G_GE": 0})
EXTRA = json.dumps({"C_DCS": [], "C_WCS": []})


class SaveS5Tests(unittest.TestCase):
    def setUp(self):
        self.storage, self.saved_dir = tempfile.mkdtemp(), player_data.DATA_DIR
        player_data.DATA_DIR = self.storage
        self.device = uuid.uuid4().hex
        self.session_id = str(uuid.uuid4())
        login = self.login()
        self.ticket, self.playfab_id = login["SessionTicket"], login["PlayFabId"]
        self.cloudscript("initializeDataS5", {"GrantInitialItems": True, "CatalogIds": ["SeasonItems_14"],
                                              "SeasonNumber": 14, "SessionId": self.session_id})

    def tearDown(self):
        player_data.DATA_DIR = self.saved_dir
        shutil.rmtree(self.storage)

    def login(self):
        with app.test_request_context():
            return auth.login_with_android_device_id(
                {"AndroidDeviceId": self.device, "CreateAccount": True, "InfoRequestParameters": INFO}, None
            ).get_json()["data"]

    def read_only(self):
        return self.login()["InfoResultPayload"]["UserReadOnlyData"]

    def cloudscript(self, name, params):
        with app.test_request_context():
            return cloudscript.execute_cloud_script({"FunctionName": name, "FunctionParameter": params,
                                                     "GeneratePlayStreamEvent": True}, self.ticket).get_json()

    def save(self, session_id=None, **sections):
        params = {"SkinCountsById": "{}", "SessionId": session_id or self.session_id, "HasSeasonPass": False}
        params.update(sections)
        return self.cloudscript("saveS5", params)

    def test_a_save_succeeds_without_error(self):
        result = self.save(Base=BASE, Game=GAME, Extra=EXTRA)
        self.assertEqual(result["code"], 200)
        self.assertEqual(result["data"], {"FunctionName": "saveS5", "FunctionResult": None})

    def test_b_next_login_returns_base(self):
        self.save(Base=BASE, Game=GAME, Extra=EXTRA)
        self.assertEqual(json.loads(self.read_only()["Base"]["Value"])["B_ACV"], 1)

    def test_c_terms_accepted_after_relogin(self):
        self.save(Base=BASE, Game=GAME, Extra=EXTRA)
        accepted = json.loads(self.read_only()["Base"]["Value"])["B_ACV"]
        # GameLoader.HaventAcceptedYet: AcceptedVersion < MinimumAcceptedVersion
        self.assertFalse(accepted < MINIMUM_ACCEPTED_VERSION)

    def test_d_game_and_extra_kept_verbatim(self):
        self.save(Base=BASE, Game=GAME, Extra=EXTRA)
        data = self.read_only()
        self.assertEqual((data["Game"]["Value"], data["Extra"]["Value"]), (GAME, EXTRA))
        self.assertEqual(data["SeasonStatsHistory"], {"Value": "{}"})

    def test_e_repeated_saves_keep_latest(self):
        for i in range(4):
            self.assertNotIn("Error", self.save(Base=BASE, Game=json.dumps({"T_S": "Done", "G_GE": i}), Extra=EXTRA)["data"])
        data = self.read_only()
        self.assertEqual(json.loads(data["Game"]["Value"])["G_GE"], 3)
        self.assertEqual(data["Base"]["Value"], BASE)

    def test_f_wrong_or_missing_session_id_rejected(self):
        self.save(Base=BASE, Game=GAME, Extra=EXTRA)
        for session_id in (str(uuid.uuid4()), ""):
            with self.subTest(session_id=session_id):
                params = {"Base": "{}", "Game": "{}", "Extra": "{}", "SkinCountsById": "{}", "HasSeasonPass": False}
                if session_id:
                    params["SessionId"] = session_id
                result = self.cloudscript("saveS5", params)
                self.assertEqual(result["code"], 200)
                self.assertEqual(result["data"]["Error"]["Error"], "JavascriptException")
                self.assertIsNone(result["data"].get("FunctionResult"))
        self.assertEqual(self.read_only()["Base"]["Value"], BASE)

    def test_f_new_session_supersedes_old_one(self):
        new_session = str(uuid.uuid4())
        self.cloudscript("initializeDataS5", {"SessionId": new_session})
        self.assertIn("Error", self.save(Base=BASE)["data"])
        self.assertNotIn("Error", self.save(session_id=new_session, Base=BASE)["data"])

    def test_g_partial_save_keeps_other_sections(self):
        self.save(Base=BASE, Game=GAME, Extra=EXTRA)
        self.assertNotIn("Error", self.save(Game=json.dumps({"T_S": "Done"}))["data"])
        data = self.read_only()
        self.assertEqual((data["Base"]["Value"], data["Extra"]["Value"]), (BASE, EXTRA))
        self.assertEqual(json.loads(data["Game"]["Value"]), {"T_S": "Done"})

    def test_g_non_string_section_rejected(self):
        self.assertIn("Error", self.save(Base={"B_ACV": 1})["data"])
        self.assertNotIn("Base", self.read_only())

    def test_new_player_login_has_no_saved_sections(self):
        self.device = uuid.uuid4().hex
        data = self.read_only()
        self.assertEqual(data, {"SeasonStatsHistory": {"Value": "{}"}})

    def test_display_name_survives_save(self):
        with app.test_request_context():
            auth.update_user_title_display_name({"DisplayName": "Tom#"}, self.ticket)
        self.save(Base=BASE, Game=GAME, Extra=EXTRA)
        self.assertEqual(self.login()["InfoResultPayload"]["AccountInfo"]["TitleInfo"]["DisplayName"], "Tom#")


if __name__ == "__main__":
    unittest.main()
