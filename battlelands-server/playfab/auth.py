import uuid
import json
import time
from flask import jsonify

# In-memory session store
_sessions = {}
_players = {}

def _make_playfab_id():
    # Real PlayFab IDs are 16 hex chars; the client converts them (TeamHelper.PlayFabIdToUInt64)
    return uuid.uuid4().hex[:16].upper()

def _make_session_ticket(playfab_id):
    return f"{playfab_id}-{uuid.uuid4().hex[:16].upper()}-{uuid.uuid4().hex.upper()}"

# InfoRequestParameters flag -> GetPlayerCombinedInfoResultPayload field (empty value for now)
_INFO_PAYLOAD_FIELDS = {
    "GetUserAccountInfo": ("AccountInfo", None),
    "GetUserInventory": ("UserInventory", []),
    "GetUserVirtualCurrency": ("UserVirtualCurrency", {}),
    "GetUserData": ("UserData", {}),
    "GetUserReadOnlyData": ("UserReadOnlyData", {}),
    "GetCharacterInventories": ("CharacterInventories", []),
    "GetCharacterList": ("CharacterList", []),
    "GetTitleData": ("TitleData", {}),
    "GetPlayerStatistics": ("PlayerStatistics", []),
    "GetPlayerProfile": ("PlayerProfile", None),
}

def _info_payload(params, playfab_id):
    payload = {"UserDataVersion": 0, "UserReadOnlyDataVersion": 0}
    for flag, (field, empty) in _INFO_PAYLOAD_FIELDS.items():
        if params.get(flag):
            payload[field] = empty
    if params.get("GetUserAccountInfo"):
        payload["AccountInfo"] = {
            "PlayFabId": playfab_id,
            "Created": "2026-01-01T00:00:00Z",
            # SetupPlayerDataFromLogin dereferences TitleInfo unchecked; DisplayName -> BattleTag ("" if empty)
            "TitleInfo": {"DisplayName": None},
        }
    if params.get("GetPlayerProfile"):
        payload["PlayerProfile"] = {"PlayerId": playfab_id}
    if params.get("GetTitleData"):
        # GameLoader.IsTooOld reads this key unchecked: Version(Application.version) < Version(value)
        # Economies.LoadConfigs reads the other keys unchecked (suffix 14 = season, 4 = game mode events)
        payload["TitleData"] = {
            "MinimumVersionAndroid": "2.9.6",
            # SkinState needs at least one entry per LevelReq list (SkinHelper.GetBattlePointsRequirementForLevel)
            "BattlePointsConfig": "{\"LevelReqCommon\":[0],\"LevelReqRare\":[0],\"LevelReqLegendary\":[0],"
                                  "\"LevelUpPriceCommon\":[0],\"LevelUpPriceRare\":[0],\"LevelUpPriceLegendary\":[0]}",
            "XtraLvlPurchase_14": "0",
            "GemsPerDogTag": "0",
            "DefaultDogTagsCapacity": "0",
            "CardPackPriceMultiplier": "1",
            "MatchBoxConfig": "{}",
            # TrophyRoadRunner..ctor: Max() over TrophiesRequired needs >= 1 element; a single high threshold keeps
            # UITrophyRoad progress/Prev(t) safe for a new player (Type left None: no icon, no exception)
            "TrophyRoadConfig_14": "[{\"RewardId\":\"TrophyRoad_1\",\"TrophiesRequired\":1000000}]",
            "ChallengeRewards_14": "{\"Daily\":[{\"ChallengeIdSuffix\":\"_1\",\"TypeString\":\"AddToGems\",\"Amount\":10}],\"DailyFallback\":{\"ChallengeIdSuffix\":\"_1\",\"TypeString\":\"AddToGems\",\"Amount\":10},\"Weekly\":[]}",
            "BattlePassRewards_14": "{}",
            "ChallengeConfig_14": "[]",
            # GameModeEventLobbyRunner.FindCurrentEvent loops forever on an empty list; needs DurationMinutes > 0
            # and TeamSize 1/2/4 (UIGameModeEvents); EventStart is recomputed by the client, so it is omitted
            "GameModeEventsConfig_4": "{\"RotationStartUTCMs\":0,\"GameModeEvents\":"
                                      "[{\"Id\":\"HeavyweightSolo\",\"DurationMinutes\":1440,\"TeamSize\":1}]}",
            # Bootstrap values (not historical): SkinShopRunner.GetNewShopContent calls GetRandom on each pool,
            # and SkinShopData.AnyIdNull treats Type None as an invalid shop. TypeString goes through Enum.Parse.
            "DailyFreeItemConfig": "{\"RewardsPool\":[{\"TypeString\":\"AddToGems\",\"Amount\":10}]}",
            "DailyFreeConsumableConfig": "{\"RewardsPool\":[{\"TypeString\":\"Consumable\",\"Amount\":1}]}",
            "ExtendedAnalyticsConfig": "{\"EnableExtendedAnalytics\":false,\"Regions\":[],\"GameModes\":[]}",
            # MatchReportRunner..ctor reads this unchecked; "{}" is enough for loading (lists used only after a match)
            "MatchReportConfig_14": "{}",
            # SkinShopRunner..ctor reads this unchecked (JSONObject array of skin ItemIds); empty = no exclusions
            "ExcludedSkinItems_14": "[]",
        }
    if params.get("GetUserReadOnlyData"):
        # SetupPlayerDataFromLogin reads this key unchecked; SetupSeasonStats needs a JSON object string
        payload["UserReadOnlyData"] = {"SeasonStatsHistory": {"Value": "{}"}}
    if params.get("GetPlayerStatistics"):
        # PlayFabRunner.CheckAndUpdateSeason: Season == 14 skips ExecuteCloudScript("startSeason14")
        payload["PlayerStatistics"] = [{"StatisticName": "Season", "Value": 14}]
    return payload

def _login(account_key, request_json):
    """Shared LoginWith* handler: LoginResult as defined by the client's PlayFab SDK 2.66."""
    request_json = request_json or {}
    player = _players.get(account_key)
    created = player is None
    if created:
        player = {"PlayFabId": _make_playfab_id(), "TitleId": request_json.get("TitleId", "")}
        _players[account_key] = player
    pf_id = player["PlayFabId"]

    session_ticket = _make_session_ticket(pf_id)
    _sessions[session_ticket] = pf_id
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    data = {
        "PlayFabId": pf_id,
        "SessionTicket": session_ticket,
        "NewlyCreated": created,
        "LastLoginTime": now,
        "EntityToken": {
            "EntityToken": uuid.uuid4().hex + uuid.uuid4().hex,
            "TokenExpiration": "2099-01-01T00:00:00Z",
            "Entity": {"Id": pf_id, "Type": "title_player_account"},
        },
        "SettingsForUser": {"NeedsAttribution": False, "GatherDeviceInfo": True, "GatherFocusInfo": True},
    }
    params = request_json.get("InfoRequestParameters")
    if params:
        data["InfoResultPayload"] = _info_payload(params, pf_id)
    return jsonify({"code": 200, "status": "OK", "data": data})

def login_with_custom_id(request_json, session_ticket=None):
    return _login("custom:" + (request_json or {}).get("CustomId", ""), request_json)

def login_with_android_device_id(request_json, session_ticket=None):
    return _login("android:" + (request_json or {}).get("AndroidDeviceId", ""), request_json)

def link_custom_id(request_json, session_ticket):
    playfab_id = _sessions.get(session_ticket)
    if not playfab_id:
        return jsonify(error("Not authorized", 401))

    custom_id = (request_json or {}).get("CustomId", "")
    _players[custom_id] = _players.get(custom_id, {})
    _players[custom_id]["PlayFabId"] = playfab_id
    _players[custom_id]["CustomId"] = custom_id

    return jsonify({
        "code": 200,
        "status": "OK",
        "data": {}
    })

def link_android_device_id(request_json, session_ticket):
    # LinkAndroidDeviceIDResult has no fields; the client maps any success to true (LinkDeviceId b__122_0)
    playfab_id = _sessions.get(session_ticket)
    if not playfab_id:
        return jsonify(error("Not authorized", 401))

    device_id = (request_json or {}).get("AndroidDeviceId", "")
    _players.setdefault("android:" + device_id, {"PlayFabId": playfab_id})

    return jsonify({
        "code": 200,
        "status": "OK",
        "data": {}
    })

def get_photon_authentication_token(request_json, session_ticket):
    playfab_id = _sessions.get(session_ticket)
    if not playfab_id:
        return jsonify(error("Not authorized", 401))

    token = str(uuid.uuid4()).replace("-", "")

    return jsonify({
        "code": 200,
        "status": "OK",
        "data": {
            # GetPhotonAuthenticationTokenResult has a single string field
            "PhotonCustomAuthenticationToken": token,
        }
    })

def error(message, code=400):
    return {
        "code": code,
        "status": "BadRequest",
        "error": message,
        "errorCode": code,
        "errorMessage": message,
    }
