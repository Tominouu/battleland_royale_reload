"""Photon custom-authentication tokens issued by GetPhotonAuthenticationToken.

The client sends the token to the Photon Master in OpAuthenticate (AuthGetParameters
"username=<PlayFabId>&token=<token>"); photon-master checks it via POST /internal/photon/validate.

Policy (bootstrap values, not historical PlayFab behaviour):
- a token stays valid for TOKEN_TTL_SECONDS and can be presented several times until then:
  our Master returns no Photon token (param 221), so LoadBalancingPeer.OpAuthenticate sends the same
  AuthGetParameters again for the next authentication (GameServer, reconnect);
- tokens live in process memory, like playfab.auth._sessions (gunicorn must run a single worker).
"""
import os
import time
import uuid

TOKEN_TTL_SECONDS = int(os.environ.get("PHOTON_TOKEN_TTL_SECONDS", 3600))

# token -> {"playfab_id", "app_id", "created_at", "expires_at"} (Unix seconds)
_tokens = {}


def _purge_expired(now):
    for token in [t for t, record in _tokens.items() if record["expires_at"] <= now]:
        del _tokens[token]


def issue_token(playfab_id, app_id, now=None):
    now = time.time() if now is None else now
    _purge_expired(now)
    token = uuid.uuid4().hex
    _tokens[token] = {
        "playfab_id": playfab_id,
        "app_id": app_id or "",
        "created_at": now,
        "expires_at": now + TOKEN_TTL_SECONDS,
    }
    return token


def validate_token(token, playfab_id, app_id, now=None):
    """Returns (valid, reason). The reason is for server logs only, never sent to the game client."""
    now = time.time() if now is None else now
    record = _tokens.get(token or "")
    if record is None:
        return False, "unknown token"
    if record["expires_at"] <= now:
        del _tokens[token]
        return False, "expired token"
    if record["playfab_id"] != playfab_id:
        return False, "PlayFabId mismatch"
    if record["app_id"] != app_id:
        return False, "AppId mismatch"
    return True, "ok"
