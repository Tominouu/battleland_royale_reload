from flask import Blueprint, request, jsonify

from playfab.auth import (
    login_with_custom_id,
    link_custom_id,
    get_photon_authentication_token,
    error,
)
from playfab.data import (
    get_user_read_only_data,
    get_user_inventory,
    get_catalog_items,
)

playfab_bp = Blueprint("playfab", __name__)

_ROUTES = {
    "/Client/LoginWithCustomID": login_with_custom_id,
    "/Client/LinkCustomID": link_custom_id,
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
    if handler is None:
        return jsonify(error(f"Unknown endpoint: {api_path}", 404))

    session_ticket = request.headers.get("X-Authorization", "")
    request_json = request.get_json(silent=True) or {}

    return handler(request_json, session_ticket)
