import time

from flask import jsonify

from playfab.auth import _sessions, error
from storage.player_data import get_read_only_data, update_read_only_data

# .NET DateTime.Ticks at the Unix epoch (100 ns units since 0001-01-01)
_DOTNET_EPOCH_TICKS = 621355968000000000


def _now_ticks():
    return _DOTNET_EPOCH_TICKS + time.time_ns() // 100


class CloudScriptError(Exception):
    """Returned as ExecuteCloudScriptResult.Error; PlayFabRX.<ExecuteCloudScript>b__17_1 turns any non-null
    Error into a PlayFabException (code 1211), which SavePlayerData reports to PlayFabRunner.ConnectionError."""

    def __init__(self, name, message):
        super().__init__(message)
        self.name = name
        self.message = message


# PlayFabRunner.SessionId: Guid generated once per app process, sent by initializeDataS5 and saveS5.
# Kept in UserReadOnlyData["SessionId"]; SetupPlayerDataFromLogin drops that key before InitPlayerData.
SESSION_ID_KEY = "SessionId"
# Serialized PlayerData sections (PlayerDataSerializer.To*JSON), read back by PlayFabRunner.InitPlayerData
SAVED_SECTIONS = ("Base", "Game", "Extra")


def _initialize_data_s5(params, playfab_id):
    if isinstance(params.get("SessionId"), str):
        update_read_only_data(playfab_id, {SESSION_ID_KEY: params["SessionId"]})
    # PlayFabRunner.<InitializeMiscellaneousData>b__55_0 deserializes this as InitializeDataResponse:
    # MatchBoxTokenDataJson must be a JSON object string, VirtualCurrency must be non-null.
    # Catalogs["SeasonItems_14"] is read unchecked by PlayFabRunner.CrosscheckAndResolvePlayerData
    return {
        # SkinRunner.ParseCatalog builds skinDatabase from these; EnsureEquippedSkinsOwned needs the six defaults
        "Catalogs": {"SeasonItems_14": [
            {"ItemId": "MrOfficeGuy", "ItemClass": "Character.Default", "VirtualCurrencyPrices": {}},
            {"ItemId": "ParachuteDefault", "ItemClass": "Parachute.Default", "VirtualCurrencyPrices": {}},
            {"ItemId": "AnimDefault", "ItemClass": "Animation.Default", "VirtualCurrencyPrices": {}},
            {"ItemId": "FlagDefault", "ItemClass": "BattleFlag.Default", "VirtualCurrencyPrices": {}},
            {"ItemId": "FootstepDefault", "ItemClass": "Footstep.Default", "VirtualCurrencyPrices": {}},
            {"ItemId": "MeleeDefault", "ItemClass": "Melee.Default", "VirtualCurrencyPrices": {}},
            # SkinShopRunner.GetNewShopContent needs 5 distinct picks; the Character branch accepts any
            # non-excluded character, so 5 characters in total let the selection loop terminate
            {"ItemId": "MrBaldWifeBeater", "ItemClass": "Character.Common", "VirtualCurrencyPrices": {}},
            {"ItemId": "MrBananaMan", "ItemClass": "Character.Common", "VirtualCurrencyPrices": {}},
            {"ItemId": "MrBunny", "ItemClass": "Character.Common", "VirtualCurrencyPrices": {}},
            {"ItemId": "MrGhostPirate", "ItemClass": "Character.Common", "VirtualCurrencyPrices": {}},
            # SkinGachaRunner.SetupChestCatalogItems finds these by ItemId; Get*ChestPrice reads
            # VirtualCurrencyPrices["GE"] unchecked. Bootstrap prices (not historical values).
            {"ItemId": "ChestBattle", "ItemClass": "Chest", "VirtualCurrencyPrices": {"GE": 100}},
            {"ItemId": "ChestBattlePremium", "ItemClass": "Chest", "VirtualCurrencyPrices": {"GE": 250}},
            {"ItemId": "ChestLucky", "ItemClass": "Chest", "VirtualCurrencyPrices": {"GE": 50}},
        ]},
        "MatchBoxTokenDataJson": "{}",
        "VirtualCurrency": {},
        "NowTicks": _now_ticks(),
    }


def _save_s5(params, playfab_id):
    # PlayFabRunner.SavePlayerData: SaveParams {Base, Game, Extra, SkinCountsById: JSON strings, SessionId,
    # HasSeasonPass}. The client ignores FunctionResult (b__78_0 is empty, b__78_2 returns true).
    # Only a save from the session registered by the latest initializeDataS5 may overwrite the player data.
    session_id = params.get("SessionId")
    if not session_id or session_id != get_read_only_data(playfab_id).get(SESSION_ID_KEY):
        raise CloudScriptError("JavascriptException", "saveS5: SessionId does not match the active session")
    sections = {k: params[k] for k in SAVED_SECTIONS if k in params}
    if not all(isinstance(v, str) for v in sections.values()):
        raise CloudScriptError("JavascriptException", "saveS5: Base, Game and Extra must be JSON strings")
    update_read_only_data(playfab_id, sections)
    return None


def _now_ticks_function(params, playfab_id):
    # PlayFabRunner.ServerNowTicks: Convert.ToInt64(FunctionResult), compared with DateTime.UtcNow.Ticks
    return _now_ticks()


def _save_match_count(params, playfab_id):
    # PlayFabRunner.HandleIncompleteMatches (login): SaveMatchCount(n) sends SaveMatchCountParams {MatchCount}
    # for matches started but not saved. The client discards the result (<HandleIncompleteMatches>b__0 returns
    # the LoginResult), so only a success without Error matters; any error ends LoginSequence in the
    # "Connection Error" popup. Any MatchCount is accepted; it is not persisted yet.
    return None


_FUNCTIONS = {
    "initializeDataS5": _initialize_data_s5,
    "nowTicks": _now_ticks_function,
    "saveMatchCount": _save_match_count,
    "saveS5": _save_s5,
}


def execute_cloud_script(request_json, session_ticket):
    playfab_id = _sessions.get(session_ticket)
    if not playfab_id:
        return jsonify(error("Not authorized", 401))

    name = (request_json or {}).get("FunctionName")
    function = _FUNCTIONS.get(name)
    if function is None:
        # Other CloudScript functions are not implemented yet (same answer as before this route existed)
        return jsonify(error("Unknown endpoint: /Client/ExecuteCloudScript", 404))

    data = {"FunctionName": name}
    try:
        data["FunctionResult"] = function((request_json or {}).get("FunctionParameter") or {}, playfab_id)
    except CloudScriptError as e:
        # A throwing CloudScript still answers HTTP 200 / code 200, with ExecuteCloudScriptResult.Error set
        data["Error"] = {"Error": e.name, "Message": e.message, "StackTrace": None}
    return jsonify({
        "code": 200,
        "status": "OK",
        "data": data,
    })
