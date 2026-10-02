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

def _accounts_path():
    d = os.path.join(DATA_DIR, "players")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "accounts.json")

def _load_accounts():
    path = _accounts_path()
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

def get_account(account_key):
    """PlayFabId linked to a login key ("android:<id>", "custom:<id>"), kept across server restarts."""
    return _load_accounts().get(account_key)

def link_account(account_key, playfab_id):
    accounts = _load_accounts()
    accounts[account_key] = playfab_id
    with open(_accounts_path(), "w") as f:
        json.dump(accounts, f)

def get_display_name(playfab_id):
    path = os.path.join(_player_path(playfab_id), "profile.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f).get("DisplayName")
    return None

def set_display_name(playfab_id, display_name):
    with open(os.path.join(_player_path(playfab_id), "profile.json"), "w") as f:
        json.dump({"DisplayName": display_name}, f)

def get_statistics(playfab_id):
    """PlayFab player statistics (name -> int value), kept across server restarts."""
    path = os.path.join(_player_path(playfab_id), "statistics.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

def set_statistic(playfab_id, name, value):
    statistics = get_statistics(playfab_id)
    statistics[name] = value
    with open(os.path.join(_player_path(playfab_id), "statistics.json"), "w") as f:
        json.dump(statistics, f)

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
