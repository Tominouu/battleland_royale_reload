"""Endpoints for our other services (photon-master), not part of the PlayFab API.

gunicorn listens on 192.168.240.1:443, which the Waydroid container (192.168.240.x) can also reach,
so callers are restricted to the host's own addresses. Never expose this without that restriction.
"""
import os

from flask import Blueprint, abort, jsonify, request

from playfab.photon_tokens import validate_token

internal_bp = Blueprint("internal", __name__)

ALLOWED_CALLERS = set(os.environ.get("INTERNAL_ALLOWED_IPS", "127.0.0.1,::1,192.168.240.1").split(","))


@internal_bp.before_request
def _only_local_callers():
    if request.remote_addr not in ALLOWED_CALLERS:
        abort(403)


@internal_bp.route("/internal/photon/validate", methods=["POST"])
def photon_validate():
    body = request.get_json(silent=True) or {}
    token, playfab_id, app_id = body.get("token"), body.get("playFabId"), body.get("appId")
    valid, reason = validate_token(token, playfab_id, app_id)
    print(f"[internal] photon validate playFabId={playfab_id} appId={app_id} -> {reason}", flush=True)
    if valid:
        return jsonify({"valid": True, "playFabId": playfab_id})
    return jsonify({"valid": False, "reason": reason})
