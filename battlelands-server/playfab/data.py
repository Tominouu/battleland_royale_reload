import json
from flask import jsonify
from storage.player_data import get_read_only_data, get_inventory, get_catalog
from playfab.auth import _sessions, error

def get_user_read_only_data(request_json, session_ticket):
    playfab_id = _sessions.get(session_ticket)
    if not playfab_id:
        return jsonify(error("Not authorized", 401))

    keys = (request_json or {}).get("Keys", None)
    data = get_read_only_data(playfab_id, keys)

    # PlayFab returns Data as a dict with Value (base64-encoded string)
    result_data = {}
    for k, v in data.items():
        if v is not None:
            import base64
            encoded = base64.b64encode(json.dumps(v).encode()).decode()
            result_data[k] = {
                "Value": encoded,
            }

    return jsonify({
        "code": 200,
        "status": "OK",
        "data": {
            "Data": result_data,
            "DataVersion": 1,
        }
    })

def get_user_inventory(request_json, session_ticket):
    playfab_id = _sessions.get(session_ticket)
    if not playfab_id:
        return jsonify(error("Not authorized", 401))

    inv = get_inventory(playfab_id)

    return jsonify({
        "code": 200,
        "status": "OK",
        "data": inv
    })

def get_catalog_items(request_json, session_ticket):
    playfab_id = _sessions.get(session_ticket)
    if not playfab_id:
        return jsonify(error("Not authorized", 401))

    catalog = get_catalog()

    return jsonify({
        "code": 200,
        "status": "OK",
        "data": catalog
    })
