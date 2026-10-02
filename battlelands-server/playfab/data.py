import json
from flask import jsonify
from storage.player_data import get_read_only_data, get_inventory, get_catalog, get_virtual_currency
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
    # PlayFabRunner.SyncInventory (after PurchaseItem) applies these balances: same persistent wallet
    inv["VirtualCurrency"] = get_virtual_currency(playfab_id)

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

# (CatalogVersion, StoreId) requested by PlayFabRunner.GetStores; only GetStoreItemsResult.Store is read
_KNOWN_STORES = {
    ("Battlebucks", "com.futureplay.battleground.virtualcurrencies2"),
    ("Battlebucks", "com.futureplay.battleground.bpstore"),
    ("Battlebucks", "com.futureplay.battleground.bundles"),
    ("SeasonItems_14", "DynamicBundleItems"),
    ("SeasonItems_14", "BattlePointsPacks"),
    ("SeasonItems_14", "EventRewards"),
}

def get_store_items(request_json, session_ticket):
    playfab_id = _sessions.get(session_ticket)
    if not playfab_id:
        return jsonify(error("Not authorized", 401))

    store = ((request_json or {}).get("CatalogVersion"), (request_json or {}).get("StoreId"))
    if store not in _KNOWN_STORES:
        return jsonify(error(f"Unknown store: {store[0]}/{store[1]}", 404))

    return jsonify({
        "code": 200,
        "status": "OK",
        "data": {
            "Store": [],
        }
    })

def get_title_news(request_json, session_ticket):
    playfab_id = _sessions.get(session_ticket)
    if not playfab_id:
        return jsonify(error("Not authorized", 401))

    # PlayFabRunner.GetTitleNewsMessages: News must be non-null; empty list skips item parsing
    return jsonify({
        "code": 200,
        "status": "OK",
        "data": {
            "News": [],
        }
    })
