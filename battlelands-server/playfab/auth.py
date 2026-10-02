import uuid
import json
import time
from flask import jsonify

from playfab.photon_tokens import issue_token
from storage.player_data import (get_account, get_display_name, get_read_only_data, get_statistics,
                                 link_account, set_display_name)

# In-memory session store
_sessions = {}
# Login key -> player; a cache of storage/players/accounts.json so accounts survive server restarts
_players = {}
# PlayFabId -> title display name (UpdateUserTitleDisplayName); keyed by PlayFabId because several
# _players entries (android:/custom: links) can share one account. Cache of players/<id>/profile.json
_display_names = {}


def _display_name(playfab_id):
    if playfab_id not in _display_names:
        _display_names[playfab_id] = get_display_name(playfab_id)
    return _display_names[playfab_id]

# PlayerData.STATISTIC_TROPHIES ("Trophies_Season" + 14): PlayFabRunner.InitPlayerData sets PlayerData.Trophies
# from this PlayerStatistics entry (0 if absent); pingNodesT updates it after each match
TROPHIES_STATISTIC = "Trophies_Season14"

# PlayFab limits for UpdateUserTitleDisplayNameRequest.DisplayName
DISPLAY_NAME_MIN_LENGTH = 3
DISPLAY_NAME_MAX_LENGTH = 25

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
            "TitleInfo": {"DisplayName": _display_name(playfab_id)},
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
            # MatchReportRunner..ctor reads this unchecked. OnMatchEnded (CONTINUE after a match) calls GetRandom on
            # BattlebucksDistribution then Rewards: both must be non-empty. Bootstrap test values, not historical.
            "MatchReportConfig_14": "{\"DailyRewardCount\":0,\"BattlebucksDistribution\":[0],"
                                    "\"Rewards\":[{\"TypeString\":\"AddToGems\",\"Amount\":0,\"Parameter\":\"\"}]}",
            # SkinShopRunner..ctor reads this unchecked (JSONObject array of skin ItemIds); empty = no exclusions
            "ExcludedSkinItems_14": "[]",
        }
    if params.get("GetUserReadOnlyData"):
        # Stored keys (SessionId, Base/Game/Extra from saveS5) as UserDataRecords; InitPlayerData reads
        # Base/Game/Extra and treats missing ones as empty JSON objects
        payload["UserReadOnlyData"] = {k: {"Value": v} for k, v in get_read_only_data(playfab_id).items()
                                       if isinstance(v, str)}
        # SetupPlayerDataFromLogin reads this key unchecked; SetupSeasonStats needs a JSON object string
        payload["UserReadOnlyData"]["SeasonStatsHistory"] = {"Value": "{}"}
    if params.get("GetPlayerStatistics"):
        # PlayFabRunner.CheckAndUpdateSeason: Season == 14 skips ExecuteCloudScript("startSeason14")
        payload["PlayerStatistics"] = [
            {"StatisticName": "Season", "Value": 14},
            {"StatisticName": TROPHIES_STATISTIC, "Value": get_statistics(playfab_id).get(TROPHIES_STATISTIC, 0)},
        ]
    return payload

def _login(account_key, request_json):
    """Shared LoginWith* handler: LoginResult as defined by the client's PlayFab SDK 2.66."""
    request_json = request_json or {}
    player = _players.get(account_key)
    if player is None and (linked_id := get_account(account_key)):
        player = _players[account_key] = {"PlayFabId": linked_id}
    created = player is None
    if created:
        player = {"PlayFabId": _make_playfab_id(), "TitleId": request_json.get("TitleId", "")}
        _players[account_key] = player
        link_account(account_key, player["PlayFabId"])
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
    link_account(custom_id, playfab_id)

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
    if "android:" + device_id not in _players and not get_account("android:" + device_id):
        link_account("android:" + device_id, playfab_id)
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

    # Bound to the PlayFabId and the requested AppId; checked by photon-master via /internal/photon/validate
    token = issue_token(playfab_id, (request_json or {}).get("PhotonApplicationId"))

    return jsonify({
        "code": 200,
        "status": "OK",
        "data": {
            # GetPhotonAuthenticationTokenResult has a single string field
            "PhotonCustomAuthenticationToken": token,
        }
    })

def update_user_title_display_name(request_json, session_ticket):
    playfab_id = _sessions.get(session_ticket)
    if not playfab_id:
        return jsonify(error("Not authorized", 401))

    # The client sends "<name>#" (PlayFabRunner.UpdateUserTitleDisplayName) and copies the returned
    # DisplayName into PlayerData.BattleTag (UILobby.SetNameSuccess)
    display_name = (request_json or {}).get("DisplayName")
    if not isinstance(display_name, str) or not DISPLAY_NAME_MIN_LENGTH <= len(display_name) <= DISPLAY_NAME_MAX_LENGTH:
        return jsonify(playfab_error(
            "InvalidParams", 1000, "Invalid input parameters",
            {"DisplayName": [f"The DisplayName field must be a string with a length between "
                             f"{DISPLAY_NAME_MIN_LENGTH} and {DISPLAY_NAME_MAX_LENGTH}."]}))

    _display_names[playfab_id] = display_name
    set_display_name(playfab_id, display_name)
    return jsonify({
        "code": 200,
        "status": "OK",
        "data": {"DisplayName": display_name},
    })

def playfab_error(name, error_code, message, details=None):
    """PlayFab error body; the client branches on errorCode (e.g. UILobby.SetNameError: 1058, 1234)."""
    body = {"code": 400, "status": "BadRequest", "error": name, "errorCode": error_code, "errorMessage": message}
    if details:
        body["errorDetails"] = details
    return body

def error(message, code=400):
    return {
        "code": code,
        "status": "BadRequest",
        "error": message,
        "errorCode": code,
        "errorMessage": message,
    }
