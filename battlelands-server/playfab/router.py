import gzip
import json
import os
import time

from flask import Blueprint, request, jsonify

from playfab.auth import (
    login_with_custom_id,
    login_with_android_device_id,
    link_custom_id,
    link_android_device_id,
    get_photon_authentication_token,
    error,
)
from playfab.data import (
    get_user_read_only_data,
    get_user_inventory,
    get_catalog_items,
)

playfab_bp = Blueprint("playfab", __name__)

_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "requests.jsonl")


def _log_request(api_path, known, request_json):
    """One JSON line per client call, to observe the real PlayFab call sequence."""
    os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
    entry = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "path": api_path,
        "known": known,
        "has_session": bool(request.headers.get("X-Authorization")),
        "has_entity_token": bool(request.headers.get("X-EntityToken")),
        "sdk": request.headers.get("X-PlayFabSDK"),
        "body": request_json,
    }
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[playfab] {api_path} {'OK' if known else 'UNKNOWN'} {json.dumps(request_json)[:300]}", flush=True)

def _request_json():
    raw = request.get_data()
    if request.headers.get("Content-Encoding", "").lower() == "gzip":
        raw = gzip.decompress(raw)
    try:
        return json.loads(raw or b"{}")
    except ValueError:
        return {"_unparsed": raw[:500].decode("utf-8", "replace")}

_ROUTES = {
    "/Client/LoginWithCustomID": login_with_custom_id,
    "/Client/LoginWithAndroidDeviceID": login_with_android_device_id,
    "/Client/LinkCustomID": link_custom_id,
    "/Client/LinkAndroidDeviceID": link_android_device_id,
    "/Client/GetPhotonAuthenticationToken": get_photon_authentication_token,
    "/Client/GetUserReadOnlyData": get_user_read_only_data,
    "/Client/GetUserInventory": get_user_inventory,
    "/Client/GetCatalogItems": get_catalog_items,
}

@playfab_bp.route("/", defaults={"path": ""}, methods=["POST"])
@playfab_bp.route("/<path:path>", methods=["POST"])
def handle_playfab(path):
    api_path = f"/{path}" if path else "/"

    handler = _ROUTES.get(api_path)
    request_json = _request_json()
    _log_request(api_path, handler is not None, request_json)
    if handler is None:
        return jsonify(error(f"Unknown endpoint: {api_path}", 404))

    session_ticket = request.headers.get("X-Authorization", "")

    return handler(request_json, session_ticket)
