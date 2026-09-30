import time

from flask import jsonify

from playfab.auth import _sessions, error

# .NET DateTime.Ticks at the Unix epoch (100 ns units since 0001-01-01)
_DOTNET_EPOCH_TICKS = 621355968000000000


def _now_ticks():
    return _DOTNET_EPOCH_TICKS + time.time_ns() // 100


def _initialize_data_s5(params):
    # PlayFabRunner.<InitializeMiscellaneousData>b__55_0 deserializes this as InitializeDataResponse:
    # MatchBoxTokenDataJson must be a JSON object string, VirtualCurrency must be non-null.
    # Catalogs["SeasonItems_14"] is read unchecked by PlayFabRunner.CrosscheckAndResolvePlayerData
    return {
        "Catalogs": {"SeasonItems_14": []},
        "MatchBoxTokenDataJson": "{}",
        "VirtualCurrency": {},
        "NowTicks": _now_ticks(),
    }


def _now_ticks_function(params):
    # PlayFabRunner.ServerNowTicks: Convert.ToInt64(FunctionResult), compared with DateTime.UtcNow.Ticks
    return _now_ticks()


_FUNCTIONS = {
    "initializeDataS5": _initialize_data_s5,
    "nowTicks": _now_ticks_function,
}


def execute_cloud_script(request_json, session_ticket):
    playfab_id = _sessions.get(session_ticket)
    if not playfab_id:
        return jsonify(error("Not authorized", 401))

    name = (request_json or {}).get("FunctionName")
    function = _FUNCTIONS.get(name)
    if function is None:
        # Other CloudScript functions are not implemented yet (same answer as before this route existed)
        return jsonify(error("Unknown endpoint: /Client/ExecuteCloudScript", 404))

    return jsonify({
        "code": 200,
        "status": "OK",
        "data": {
            "FunctionName": name,
            "FunctionResult": function((request_json or {}).get("FunctionParameter") or {}),
        }
    })
