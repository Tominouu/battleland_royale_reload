import uuid
import json
import time
from flask import jsonify

# In-memory session store
_sessions = {}
_players = {}

def _make_playfab_id():
    return str(uuid.uuid4())

def _make_session_ticket():
    return str(uuid.uuid4()).replace("-", "").upper()

def login_with_custom_id(request_json):
    custom_id = (request_json or {}).get("CustomId", "")
    title_id = (request_json or {}).get("TitleId", "")

    player = _players.get(custom_id)
    if not player:
        pf_id = _make_playfab_id()
        created = True
    else:
        pf_id = player["PlayFabId"]
        created = False

    session_ticket = _make_session_ticket()
    entity_token = str(uuid.uuid4()).replace("-", "")

    _players[custom_id] = {
        "PlayFabId": pf_id,
        "CustomId": custom_id,
        "TitleId": title_id,
        "Created": created,
    }
    _sessions[session_ticket] = pf_id

    return jsonify({
        "code": 200,
        "status": "OK",
        "data": {
            "SessionTicket": session_ticket,
            "PlayFabId": pf_id,
            "NewlyCreated": created,
            "EntityToken": {
                "EntityToken": entity_token,
                "TokenExpiration": "2099-01-01T00:00:00Z",
            },
            "SettingsForUser": {
                "NeedsAttribution": False,
                "GatherDeviceInfo": True,
            },
        }
    })

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
            "PhotonAuthenticationToken": {
                "Token": token,
            }
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
