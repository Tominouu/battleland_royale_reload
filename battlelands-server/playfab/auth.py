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
