# Battlelands private server

Private server for **Battlelands Royale v2.9.6** (Unity 2018.4.31f1, IL2CPP): a PlayFab-compatible HTTPS backend
and a Photon Master/GameServer, used by the original Android client with a minimal set of patches.

## Current status

Validated end to end at commit `d8074af` with the real client, under Waydroid on an x86_64 Linux host:

**Login → lobby → matchmaking → GameServer → Quantum match → "Winner" screen → CONTINUE → back to the
Photon Master → "Match ended" screen → CONTINUE → lobby (Match Report shown).**

The following works with the private infrastructure:

- the original 2.9.6 APK, patched to talk to the private servers (see [Client setup](#client-setup));
- PlayFab login (`LoginWithAndroidDeviceID`), display name, accounts persisted on disk;
- Photon custom authentication: a token is issued by the backend and checked by photon-master;
- matchmaking: JoinRandom (always "no match"), then CreateGame on the Master, then a room on the GameServer;
- Quantum: SimulationStart, and each client input is relayed back to the client;
- a full match, the end-of-match CloudScript calls (`pingNodesT`, `saveS5`), LeaveRoom, reconnection to the
  Master and the return to the lobby.

Many services are only **bootstrap/minimal** (rewards, progression, store, friends, etc.): they return just
what the client needs to keep running. See [Known limitations](#known-limitations). The rest of the game
(other game modes, custom battles, social features) was not tested and is not listed as working.

### Screenshots

The original 2.9.6 client running against the private PlayFab backend and Photon Master/GameServer (Waydroid).

| | |
|:---:|:---:|
| ![Lobby](docs/screenshots/01-lobby.jpg) | ![Tutorial with Ruby](docs/screenshots/02-tutorial-ruby.jpg) |
| Lobby after login, BattleTag set | Tutorial, before the first training battle |
| ![Training battle map](docs/screenshots/03-training-battle-map.jpg) | ![Parachute drop](docs/screenshots/04-parachute.jpg) |
| Training battle: drop zone selection | Parachute drop |
| ![In-game tutorial](docs/screenshots/05-tutorial-ingame.jpg) | ![Combat HUD](docs/screenshots/06-combat-hud.jpg) |
| In-game tutorial | Combat with HUD and practice bots |
| ![Multiplayer Select Item](docs/screenshots/multiplayer/1.png) | ![Preparing Matchmaking](docs/screenshots/multiplayer/2.png) |
| Multiplayer Select Item | Preparing Matchmaking|
| ![Multiplayer battle](docs/screenshots/multiplayer/3.png) | ![Spawn](docs/screenshots/multiplayer/4.png) |
| Multiplayer battle in progress | Spawn |
| ![Player interaction](docs/screenshots/multiplayer/5.png) | ![Multiplayer game](docs/screenshots/multiplayer/6.png) |
| Player interaction during a multiplayer match | Multiplayer game |
| ![Multiplayer fight](docs/screenshots/multiplayer/7.png) | ![New area alert](docs/screenshots/multiplayer/8.png) |
| Multiplayer fight | New area alert |

## Architecture

```
Android client (Waydroid)            original APK 2.9.6 + libmain.so redirect + patched metadata/libil2cpp
    │  HTTPS 443   https://b.127-0-0-1.sslip.io  (resolved to 192.168.240.1 by the Waydroid hosts overlay)
    ▼
PlayFab-compatible backend           battlelands-server/  (Flask, served by gunicorn, TLS)
    │  Photon token                  GetPhotonAuthenticationToken; photon-master checks it with
    │                                POST /internal/photon/validate
    ▼
Photon Master  TCP 4530              photon-master/server.py  (Protocol16, DH + AES, OpAuthenticate)
    │  CreateGame → GameServer address 192.168.240.1:4531
    ▼
Photon GameServer  TCP 4531          same process: room join, RaiseEvent, LeaveRoom
    │  Event 100 / 102
    ▼
Quantum simulation                   runs in the client (deterministic lockstep); photon-master/quantum.py
                                     sends SimulationStart and relays each client's inputs
```

- The client resolves the PlayFab URL from `global-metadata.dat` (patched to `https://b.127-0-0-1.sslip.io`).
- The client gets the Photon Master address from `libmain.so`, which hooks `PhotonNetwork.ConnectToRegion`
  and connects over TCP to the address compiled in (`192.168.240.1:4530`).
- `192.168.240.1` is the host side of the Waydroid bridge (`waydroid0`).

## Requirements

What the validated environment actually uses:

| Component | Version / details |
|---|---|
| Host | Linux x86_64 (validated environment: Ubuntu-based, `sudo` available) |
| Android runtime | [Waydroid](https://waydro.id) (1.6.2 here, Android 13), **with ARM translation** (`libndk_translation`): the APK only ships `arm64-v8a` libraries. Bridge `waydroid0` = `192.168.240.1/24`, `mount_overlays = True` in `/var/lib/waydroid/waydroid.cfg` |
| Python | 3.10 or newer (code uses `X \| None` annotations); validated with Python 3.14.4 |
| Backend Python packages | `flask`, `flask-cors`, `gunicorn`, in the virtualenv `battlelands-server/venv` (validated: Flask 3.1.3, flask-cors 6.0.5, gunicorn 26.2.0) |
| photon-master / client tools | system `python3` with the `cryptography` package (validated: 46.0.5) |
| Native build of `libmain.so` | **either** the Android NDK r21+ (`client-patch/native/build.sh`) **or** `clang` with an aarch64 target plus an LLD linker, e.g. rustup's `rust-lld` (`client-patch/native/build-local.sh`, the one used for the validated client) |
| Other tools | `openssl` (TLS certificates), `unzip` |
| Optional | `tcpdump` (network captures) |
| **Not versioned** | the original APK `Battlelands Royale 2.9.6` (`com.futureplay.battleground`, version code 668). The validated build used the APKPure file, SHA-256 `a4aa27b17166135dbc601e762be909fcb1697decc0a0c9b5b8f782dcd7057c23`. `*.apk` is git-ignored: you must provide it yourself. |

Ports:

| Port | Service | Listening on |
|---|---|---|
| 443/TCP | Backend HTTPS (PlayFab API + `/internal/photon/validate`) | `192.168.240.1` (gunicorn `-b`) |
| 4530/TCP | Photon Master | `0.0.0.0` (default `--host`) |
| 4531/TCP | Photon GameServer | `0.0.0.0` (default `--host`) |

No Android SDK or `adb` is needed for the Waydroid setup: the client is installed and started with
`waydroid` commands.

## Installation

All commands are run from the repository root unless stated otherwise.

### 1. Clone and install the Python dependencies

```bash
git clone <repository-url> battleland_royale_reload
cd battleland_royale_reload

python3 -m venv battlelands-server/venv
battlelands-server/venv/bin/pip install flask flask-cors gunicorn

python3 -c "import cryptography"   # needed by photon-master and client-patch; install it if this fails
```

### 2. TLS certificates (not versioned)

The client validates the backend certificate for `b.127-0-0-1.sslip.io`, and photon-master calls the
backend at `https://192.168.240.1`. The validated setup uses a private test CA (the actual files were
generated with a one-off script that is not in the repository). These `openssl` commands produce
equivalent files, in the location photon-master expects by default (`build/tls/ca.pem`):

```bash
mkdir -p build/tls && cd build/tls
HOST=b.127-0-0-1.sslip.io; IP=192.168.240.1

openssl req -x509 -newkey rsa:2048 -nodes -keyout ca.key -out ca.pem -days 3650 \
  -subj "/CN=Battlelands Private Test CA" \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:0" -addext "keyUsage=critical,keyCertSign,cRLSign"
openssl req -newkey rsa:2048 -nodes -keyout server.key -out server.csr -subj "/CN=$HOST"
printf "subjectAltName=DNS:$HOST,IP:$IP\nbasicConstraints=CA:FALSE\nextendedKeyUsage=serverAuth\n" > server.ext
openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial -days 397 -sha256 \
  -extfile server.ext -out server.pem
cat ca.pem >> server.pem                                               # serve the chain
cp ca.pem "$(openssl x509 -in ca.pem -noout -subject_hash_old).0"      # Android CA file name
cd ../..
```

`build/` is git-ignored. Keep `ca.key` private.

### 3. Waydroid: hosts and CA overlays

The client must resolve `b.127-0-0-1.sslip.io` to the host bridge and trust the test CA. This is done with
Waydroid system overlays, so the Android image itself is not modified:

```bash
O=/var/lib/waydroid/overlay/system/etc
printf '127.0.0.1       localhost\n::1             ip6-localhost\n192.168.240.1   b.127-0-0-1.sslip.io\n' \
  | sudo tee $O/hosts >/dev/null
sudo mkdir -p $O/security/cacerts
sudo install -m 644 -o root -g root build/tls/*.0 $O/security/cacerts/

waydroid session stop && waydroid session start   # overlays are only applied when the rootfs is mounted
```

To revert, delete these two files and restart the Waydroid session. Details: [docs/15_PLAYFAB_LOGIN.md](docs/15_PLAYFAB_LOGIN.md).

### 4. Build the client APK

The original APK is not modified in place. `make_apk.py` builds a new APK from it with four changes:

1. **`libmain.so`**: the original file is kept, renamed `libmain_orig.so`, and our redirect library is added as
   `libmain.so` (`client-patch/native/blr_redirect.c`). It redirects the Photon connection to a fixed IP and port.
2. **`global-metadata.dat`** (`patch_metadata.py`): the PlayFab URL is redirected to the backend host and
   the Photon AppId literal is replaced.
3. **`libil2cpp.so`**, patch 1 (`patch_il2cpp_gps.py`): `GooglePlayServicesChecker.UpToDate()` always
   returns true. Without it, boot stays at "1" because Waydroid has no Google Play Services.
4. **`libil2cpp.so`**, patch 2 (`patch_il2cpp_analytics.py`): the four Firebase Analytics wrappers
   become no-ops. Without it, the game keeps restarting its loading routine.

```bash
APK=/path/to/battlelands-royale-2.9.6.apk     # original APK, not provided by this repository
W=build/client; mkdir -p $W

# 1. libmain.so pointing at the Photon Master (validated: 192.168.240.1 4530)
LLD=$(ls ~/.rustup/toolchains/*/lib/rustlib/x86_64-unknown-linux-gnu/bin/rust-lld | head -1) \
  client-patch/native/build-local.sh 192.168.240.1 4530
#   or, with the NDK:  ANDROID_NDK_HOME=/path/to/ndk client-patch/native/build.sh 192.168.240.1 4530

# 2-4. extract, then patch metadata and libil2cpp
unzip -o -q "$APK" lib/arm64-v8a/libil2cpp.so assets/bin/Data/Managed/Metadata/global-metadata.dat -d $W
python3 client-patch/patch_metadata.py $W/assets/bin/Data/Managed/Metadata/global-metadata.dat \
  b.127-0-0-1.sslip.io -o $W/global-metadata.dat
python3 client-patch/patch_il2cpp_gps.py $W/lib/arm64-v8a/libil2cpp.so $W/libil2cpp.gps.so
python3 client-patch/patch_il2cpp_analytics.py $W/libil2cpp.gps.so $W/libil2cpp.so

# assemble and sign (APK Signature Scheme v2, test key created in --keydir if absent)
python3 client-patch/make_apk.py "$APK" client-patch/native/out/libmain.so $W/global-metadata.dat \
  --replace lib/arm64-v8a/libil2cpp.so=$W/libil2cpp.so \
  -o $W/battlelands-private.apk --keydir $W/keys
```

`patch_il2cpp_gps.py` checks the SHA-256 of the original `libil2cpp.so` and stops on any other file. Keep
the same `--keydir` for later builds: Android only installs an update over an app signed with the same key.

With the APK above, this sequence rebuilds a client whose content (every entry except the signature) is
identical to the client used for the validation.

## Configuration

Addresses are compiled into the client or passed on the command line; there is no central configuration file.

| Value | Where | Validated value | Required / default |
|---|---|---|---|
| Backend host name | `patch_metadata.py` argument, server certificate (CN/SAN), Waydroid hosts overlay | `b.127-0-0-1.sslip.io` | **Must be identical** in all three. The name is only resolved through the overlay, so any name works if these three agree. |
| Backend IP | gunicorn `-b`, certificate SAN IP, hosts overlay, `--validate-url` of photon-master | `192.168.240.1` | Must be an address the Waydroid container can reach (the `waydroid0` bridge). Specific to this environment. |
| Photon Master address | `build-local.sh` / `build.sh` arguments (compiled into `libmain.so`) | `192.168.240.1 4530` | Port defaults to 4530. Rebuild the APK to change it. |
| GameServer address sent to clients | `photon-master/server.py --game-address` | `192.168.240.1:4531` (default) | Must match `--game-port` and be reachable from Waydroid. |
| Backend validation URL | `photon-master/server.py --validate-url` | `https://192.168.240.1/internal/photon/validate` (default) | Must match the backend address and certificate. |
| Backend CA for photon-master | `photon-master/server.py --backend-ca` | `build/tls/ca.pem` (default) | |
| Quantum RuntimeConfig | `photon-master/server.py --quantum-runtime-config` | Default path `build/quantum-probe-test/logs/runtimeconfig-1707.bin` (not versioned) | On a clean clone, pass the versioned copy `photon-master/tests/fixtures/runtimeconfig-1707.bin` (same bytes). Without it, SimulationStart is disabled and matches never start. |
| Callers allowed on `/internal/*` | environment variable `INTERNAL_ALLOWED_IPS` (backend) | `127.0.0.1,::1,192.168.240.1` (default) | `/internal/photon/validate` must not be reachable from the client network, hence this restriction. |
| Photon token lifetime | environment variable `PHOTON_TOKEN_TTL_SECONDS` (backend) | `3600` (default) | |
| Photon AppId | `patch_metadata.py` (literal replaced by Reborn's AppId) | fixed in the script | No change needed; the backend binds each token to the AppId the client sends. |
| PlayFab TitleId | sent by the client | not used for routing | `TITLE_ID` in `battlelands-server/config/settings.py` (`FC88D`) is not used by the code. |

No secret is stored in the repository. `build/tls/*.key`, the APK signing key (`--keydir`), the logs and
`battlelands-server/storage/players/` stay local (git-ignored).

## Running

Start Waydroid first: the `waydroid0` bridge (`192.168.240.1`) must exist before gunicorn can bind to it.

### Backend

Port 443 needs root to bind. gunicorn then switches its worker to your user. Keep **one worker**
(`-w 1`): sessions and Photon tokens are kept in process memory.

```bash
R=$(pwd); mkdir -p battlelands-server/logs
sudo "$R/battlelands-server/venv/bin/gunicorn" --chdir "$R/battlelands-server" \
  --user "$(id -u)" --group "$(id -g)" -w 1 -b 192.168.240.1:443 \
  --certfile "$R/build/tls/server.pem" --keyfile "$R/build/tls/server.key" \
  --access-logfile "$R/battlelands-server/logs/access.log" \
  --error-logfile "$R/battlelands-server/logs/server.log" --capture-output app:app
```

Logs are written to `battlelands-server/logs/`:

- `requests.jsonl`: one line per PlayFab call, with `known: false` for unimplemented endpoints;
- `server.log`;
- `access.log`.

Quick check from the host:

```bash
curl --cacert build/tls/ca.pem --resolve b.127-0-0-1.sslip.io:443:192.168.240.1 https://b.127-0-0-1.sslip.io/
# {"service":"Battlelands Private Server","status":"running"}
```

`kill -HUP <gunicorn master pid>` reloads the code. Sessions are lost on reload; accounts and display
names are kept on disk.

### Photon Master/GameServer

```bash
python3 photon-master/server.py \
  --quantum-runtime-config photon-master/tests/fixtures/runtimeconfig-1707.bin
```

One process serves the Master (4530) and the GameServer (4531). It logs to stdout; add `-v` to also dump every
outgoing frame in hex. On startup it prints `[QUANTUM] RuntimeConfig … byte[1707]` and
`MASTER listening on ('0.0.0.0', 4530)` / `GAME listening on ('0.0.0.0', 4531)`.

### Client Android

See [Client setup](#client-setup).

## Client setup

Install the APK built in [Installation § 4](#4-build-the-client-apk) into Waydroid, then start it:

```bash
mkdir -p ~/.local/share/waydroid/data/waydroid_tmp          # = /data/waydroid_tmp inside Android
cp build/client/battlelands-private.apk ~/.local/share/waydroid/data/waydroid_tmp/
sudo waydroid shell -- pm install -r /data/waydroid_tmp/battlelands-private.apk
sudo waydroid shell -- pm path com.futureplay.battleground   # check that the install really happened

waydroid app launch com.futureplay.battleground
```

- If another build of `com.futureplay.battleground` is installed with a different signature (for example
  Battlelands Reborn), uninstall it first:
  ```bash
  sudo waydroid shell -- pm uninstall com.futureplay.battleground
  ```
- `waydroid app install` does not report install failures; use `pm install` as above and check with `pm path`.
- Client logs:
  ```bash
  sudo waydroid shell -- logcat -v threadtime
  ```
  The redirect library logs with the tag `BLRRedirect`.

## Verification

- [ ] **Backend starts**: the `curl` above returns `"status":"running"`.
- [ ] **Photon Master starts**: listening on 4530 and 4531; `RuntimeConfig … byte[1707]` is logged (not "SimulationStart disabled").
- [ ] **Client connects**: `/Client/LoginWithAndroidDeviceID` appears in `battlelands-server/logs/requests.jsonl`.
- [ ] **Login works**: photon-master logs `MASTER connection from …`, then `accepted -> OperationResponse 230 ReturnCode=0`.
- [ ] **Lobby appears**: the display name is shown (asked once for a new account) and the BATTLE button is visible.
- [ ] **Matchmaking works**: `JoinRandomRoom -> NO_MATCH`, then `opcode=227` on the Master and the client
      closes the Master connection.
- [ ] **GameServer works**: `GAME connection from …`, 230 accepted, `opcode=227`, `Join event sent actor=1`.
- [ ] **Quantum match starts**: `S>C probe`, then `S>C SimulationStart event 100 byte[1800]`.
- [ ] **Gameplay works**: a steady stream of `S>C relay tick=…` lines, and the character can be played.
- [ ] **End of match works**: "Winner" screen; after CONTINUE, `pingNodesT` and `saveS5` in `requests.jsonl`,
      then `opcode=254`, `LeaveRoom -> OK` and `closed by client` on the GameServer connection.
- [ ] **Return to lobby works**: a new `MASTER connection from …` with 230 accepted, the "#N Match ended!" screen,
      and after the second CONTINUE the lobby with the Match Report.

The end-to-end validation used an existing account whose tutorial state (`T_S` in the `Game` value of
`battlelands-server/storage/players/<PlayFabId>/readonly_data.json`) was `Skipped`. A new account starts
with the tutorial (see the screenshots); the full tutorial was not part of the end-to-end validation.

## Tests

```bash
python3 photon-master/tests/test_auth.py          # Photon framing/auth/GameServer (starts a fake backend)
python3 photon-master/tests/test_quantum.py       # Quantum BitStream, SimulationStart, inputs
(cd battlelands-server && venv/bin/python -m unittest discover tests)
```

Add `-v` for per-test output. At `d8074af`: 32, 30 and 38 tests, all passing (each command prints
`Ran N tests` and `OK`).

## Troubleshooting

| Symptom | Known cause / fix |
|---|---|
| Boot stays at "1" | Google Play Services check: the client was built without `patch_il2cpp_gps.py` ([docs/14](docs/14_REBORN_IL2CPP_PATCHES.md)). |
| The game keeps restarting its loading routine | Firebase Analytics without Play Services: apply `patch_il2cpp_analytics.py`. |
| Login fails, `UnknownHostException` in logcat | Hosts overlay not active: restart the Waydroid **session** (`waydroid session stop` / `start`; a container restart is not enough). If Android reports `Active default network: none`, restarting the session also fixes it. |
| TLS error on login | The CA is missing from `/var/lib/waydroid/overlay/system/etc/security/cacerts/` (file name = `subject_hash_old` + `.0`), or the server certificate does not cover the host name compiled into the metadata. |
| photon-master: `backend unavailable` / `backend rejected` on 230 | Backend not running or not reachable at `--validate-url`, wrong `--backend-ca`, or the caller IP is not in `INTERNAL_ALLOWED_IPS` (HTTP 403). |
| Match never starts after joining the room | photon-master was started without a RuntimeConfig (`SimulationStart disabled` warning): pass `--quantum-runtime-config photon-master/tests/fixtures/runtimeconfig-1707.bin`. |
| Stuck after CONTINUE on the "Match ended" screen, client still connected to the GameServer | GameServer without the LeaveRoom (254) response: use photon-master at `d8074af` or later. |
| New account / display name lost after a backend restart | Fixed since `65d07ca`: device links and display names are stored in `battlelands-server/storage/players/` (`accounts.json`, `<PlayFabId>/profile.json`). This directory is git-ignored: back it up. |
| "Connection Error" popup at login | A CloudScript function returned an error. Check `requests.jsonl` / `server.log` for the function name. |
| `waydroid app install` seems to succeed but the old app is still there | Use `pm install -r` (see [Client setup](#client-setup)) and check `pm path`; a different signature needs `pm uninstall` first. |
| Files become owned by root after `sudo waydroid shell` | `waydroid shell` (lxc-attach) changes the owner of the files its stdio points to: run it as `( sudo waydroid shell -- cmd ) </dev/null 2>&1 \| cat`. |

## Known limitations

- **One human player per room.** JoinRandom always answers "no match" and each CreateGame creates a new room.
  The GameServer puts the client in it as actor 1; there is no room manager. The other battlers come from the
  game itself, not from other connected players.
- **Quantum is not simulated on the server.** photon-master sends one SimulationStart, with the RuntimeConfig
  captured from the real client, and relays each input tick back once. Quantum reconnection is not supported.
- **Rewards and progression are placeholders.** `pingNodesT` returns `{}`, so a match gives 0 trophies and
  0 Match Tokens. TitleData values such as `MatchReportConfig_14`, `TrophyRoadConfig_14`, the challenge
  rewards and the daily free items are bootstrap values chosen to keep the client running, not the
  original game data. `saveMatchCount` accepts the call but stores nothing.
- **Economy, store and inventory are minimal.** Virtual currencies are empty (0 coins, 0 gems), the catalog only
  holds the default skins, a few characters and three chests with bootstrap prices, every store is empty,
  and there are no purchases.
- **Endpoints not implemented** answer HTTP 200 with an error body (`code` 404, "Unknown endpoint"). The client
  currently tolerates this for `GetFriendsList` and `ReportDeviceInfo`. CloudScript functions other than
  `initializeDataS5`, `nowTicks`, `pingNodesT`, `saveMatchCount` and `saveS5` get the same answer.
- **Sessions and Photon tokens are in memory** (single gunicorn worker). A backend restart requires the client
  to log in again (restart the game).
- **Firebase, ads and analytics** are not available in this setup (the client logs warnings; analytics
  calls are disabled by the patch).
- **Tested only under Waydroid** (x86_64 host, ARM translation). Addresses are compiled into the client: changing
  them requires rebuilding the APK.
- Not tested: tutorial completion, custom battles, other game modes, social/friends, clans, chat, purchases.

## Project structure

```
battlelands-server/            PlayFab-compatible backend (Flask app, run with gunicorn)
├── app.py                     Flask entry point (PlayFab blueprint + /internal blueprint)
├── playfab/
│   ├── router.py              /Client/* dispatcher; logs every call to logs/requests.jsonl
│   ├── auth.py                Login, account linking, display name, Photon token, TitleData
│   ├── data.py                Read-only data, inventory, catalog, stores, title news
│   ├── cloudscript.py         ExecuteCloudScript functions
│   ├── photon_tokens.py       Photon custom-auth tokens (in memory, TTL)
│   └── internal.py            POST /internal/photon/validate (host-only)
├── storage/                   player_data.py, catalog.json; players/ (accounts, git-ignored)
├── config/settings.py         HOST/PORT for `python app.py` (Flask dev server, not used with gunicorn)
├── tests/                     unittest suite
└── scripts/                   Earlier Android-emulator (AVD) workflow: setup.sh, start-emulator.sh,
                               install-game.sh, run-game.sh, collect-logcat.sh, run-server.sh,
                               setup-hosts.sh, ANDROID_SETUP.md. Not used by the validated Waydroid
                               setup; several scripts have hardcoded /home/tom/... paths.
photon-master/                 Photon Master + GameServer (asyncio, single file) and Quantum codec
├── server.py                  framing, DH/AES, custom auth, matchmaking, GameServer, LeaveRoom
├── quantum.py                 Quantum BitStream, SimulationStart, input encoding
└── tests/                     test_auth.py, test_quantum.py, fixtures/ (incl. runtimeconfig-1707.bin)
client-patch/                  Client build tooling (see Installation § 4)
├── native/                    blr_redirect.c (libmain.so redirect), build.sh (NDK), build-local.sh (clang + LLD)
├── patch_metadata.py          global-metadata.dat: PlayFab URL + Photon AppId
├── patch_il2cpp_gps.py        libil2cpp.so: Google Play Services check bypass
├── patch_il2cpp_analytics.py  libil2cpp.so: Firebase Analytics wrappers disabled
└── make_apk.py                rebuilds and v2-signs the APK from the original
docs/                          Reverse-engineering notes (index: docs/00_index.md), screenshots
TODO.md                        Early research TODO list (partly outdated)
```

### Reverse-engineering notes

Detailed analysis lives in [`docs/`](docs/00_index.md); in particular:

- [13_MINIMAL_REDIRECT.md](docs/13_MINIMAL_REDIRECT.md): client redirect;
- [14_REBORN_IL2CPP_PATCHES.md](docs/14_REBORN_IL2CPP_PATCHES.md): libil2cpp patches;
- [15_PLAYFAB_LOGIN.md](docs/15_PLAYFAB_LOGIN.md): TLS, overlay and login;
- [BOOT_SEQUENCE.md](docs/BOOT_SEQUENCE.md);
- [SERVER_REQUIREMENTS.md](docs/SERVER_REQUIREMENTS.md).

Key findings:

- **Engine**: Unity 2018.4.31f1, IL2CPP backend
- **Backend**: PlayFab (SDK v2.66.190509) for auth + data
- **Networking**: Photon PUN classic 1.92 (TCP, Protocol16) + Quantum (deterministic lockstep)
- **Config**: Firebase Remote Config for runtime overrides
- **Auth**: the 2.9.6 client logs in with `LoginWithAndroidDeviceID` (CustomID and Facebook paths also exist)
- **Methods identified**: `LoginWithCustomOrDeviceId`, `ConfigLoader.FetchFirebaseConfigs`, `OverrideCacheWithFirebaseConfigs`
- **Local server support**: `LocalApiServer` property + `playfab.local.settings.json`
