import os
import json

DATA_DIR = os.path.join(os.path.dirname(__file__))

def _player_path(playfab_id):
    d = os.path.join(DATA_DIR, "players", playfab_id)
    os.makedirs(d, exist_ok=True)
    return d

def get_read_only_data(playfab_id, keys=None):
    path = os.path.join(_player_path(playfab_id), "readonly_data.json")
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
    else:
        data = {}
    if keys:
        return {k: data.get(k) for k in keys}
    return data

def update_read_only_data(playfab_id, data):
    path = os.path.join(_player_path(playfab_id), "readonly_data.json")
    existing = {}
    if os.path.exists(path):
        with open(path) as f:
            existing = json.load(f)
    existing.update(data)
    with open(path, "w") as f:
        json.dump(existing, f)

def get_inventory(playfab_id):
    path = os.path.join(_player_path(playfab_id), "inventory.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"Inventory": [], "VirtualCurrency": {}, "VirtualCurrencyRechargeTimes": {}}

def get_catalog():
    path = os.path.join(DATA_DIR, "catalog.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"Catalog": []}

def save_session(playfab_id, session_ticket):
    path = os.path.join(_player_path(playfab_id), "session.json")
    with open(path, "w") as f:
        json.dump({"SessionTicket": session_ticket, "PlayFabId": playfab_id}, f)

def get_session(playfab_id):
    path = os.path.join(_player_path(playfab_id), "session.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None
