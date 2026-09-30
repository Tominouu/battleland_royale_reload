# 12 — Battlelands Reborn APK Analysis

> Addendum to the original Battlelands Royale 2.9.6 reverse-engineering documentation.
>
> This document must be read together with `docs/00_index.md` → `docs/11_diagram.md`,
> `docs/BOOT_SEQUENCE.md`, `docs/SERVER_REQUIREMENTS.md`, and the other reverse-engineering
> artifacts in this repository.

## 1. Purpose

This document records the reverse-engineering findings obtained from the **Battlelands Reborn** APK.

The important discovery is that Battlelands Reborn is based on the original **Battlelands Royale 2.9.6** client and adds a custom native module rather than replacing the complete game.

The custom module:

1. loads the original Unity native library;
2. waits for IL2CPP;
3. resolves Unity/IL2CPP classes and methods dynamically;
4. hooks the Photon connection path;
5. redirects Photon connections to a private server;
6. works with a PlayFab-compatible private backend;
7. leaves the original Unity/IL2CPP gameplay code intact.

---

## 2. Reference APK

Project:

`https://github.com/Neiky42/battlelands-reborn`

Release:

`Battlelands Reborn`

Tag:

`battlelands`

Release date:

`2026-09-10`

APK:

`Battlelands.Reborn.64.bits.apk`

Architecture:

`arm64-v8a`

Size:

`155,805,463 bytes`

SHA-256:

```text
c16ebe6af45829396886e1409910b78b7afa5dff6b38a7f6ede342d628fe9b7a
```

The APK is kept at the repository root:

```text
Battlelands.Reborn.64.bits.apk
```

---

## 3. Relationship with the Original Client

The large Unity/IL2CPP components appear unchanged while the native Android entry module is replaced.

Important files:

```text
lib/arm64-v8a/libmain.so
lib/arm64-v8a/libmain_orig.so
lib/arm64-v8a/libil2cpp.so
global-metadata.dat
```

The original native entry library is preserved as:

```text
libmain_orig.so
```

The custom Reborn module is:

```text
libmain.so
```

The original client remains responsible for:

- Unity
- IL2CPP
- gameplay
- Quantum
- Photon client SDK
- PlayFab SDK
- UI
- assets
- weapons
- maps

---

## 4. Native Library Comparison

### Original `libmain_orig.so`

Observed characteristics:

```text
~6 KB
NDK r16b
Unity Technologies 2018.4.31f1
```

### Reborn `libmain.so`

Observed characteristics:

```text
748,952 bytes
~749 KB
NDK r27c
clang 18
```

Identified symbols/functions include:

```text
photon_init
load_combat
clan_tic
carte_tic
attendre_il2cpp
detourner
ui_construire
```

---

## 5. Boot Relay

The custom library does not replace Unity startup.

Architecture:

```text
Android
   |
   v
libmain.so
   |
   +-- JNI_OnLoad
   +-- store JavaVM
   +-- dlopen(libmain_orig.so)
   +-- resolve original JNI_OnLoad
   +-- call original JNI_OnLoad
             |
             v
       Normal Unity startup
```

Observed `JNI_OnLoad` address:

```text
0xa8140
```

The custom module therefore wraps the original Unity native entry point.

---

## 6. IL2CPP Initialization

The custom initialization path uses:

```text
attendre_il2cpp
```

Observed address:

```text
0xa8218
```

It waits for `libil2cpp.so`, attaches the thread to the runtime, and waits for:

```text
FuturePlay.AudioManager
```

A detour is installed on:

```text
FuturePlay.AudioManager.Update
```

The original function pointer is stored around:

```text
0xdccc50
```

The initialization loop then installs the Photon hooks.

---

## 7. IL2CPP Reflection

Reborn does not require direct modification of `libil2cpp.so`.

It uses IL2CPP exports to resolve classes and methods dynamically.

Relevant APIs include:

```text
il2cpp_domain_get
il2cpp_class_from_name
il2cpp_runtime_invoke
il2cpp_field_static_get_value
```

General mechanism:

```text
Assembly + Namespace + Class + Method
                 |
                 v
          IL2CPP reflection
                 |
                 v
          Runtime object
                 |
                 v
      il2cpp_runtime_invoke(...)
```

This allows the native module to interact with existing C# code without hardcoding every IL2CPP address.

---

## 8. IL2CPP Invocation Wrapper

The module contains:

```text
appeler
```

Observed address:

```text
0x9c00c
```

It wraps:

```text
il2cpp_runtime_invoke
```

and handles:

- argument preparation;
- value types;
- method invocation;
- exception retrieval;
- error logging.

---

## 9. Photon Initialization — Important Correction

`photon_init` is **not** the actual Photon connection redirect.

It is mainly a lazy initializer for Photon lobby/custom-room functionality.

It resolves/caches methods such as:

```text
PhotonNetwork.get_room
PhotonNetwork.get_isMasterClient
RoomInfo.get_CustomProperties
Room.SetCustomProperties
Hashtable constructor
Hashtable.get_Item
Hashtable.set_Item
```

It is used by functions such as:

```text
salon_publier
```

to publish custom room properties such as map selection.

The actual network redirect is installed by `eu_installer`.

---

## 10. Photon Redirect Initialization

The actual redirect is installed by:

```text
eu_installer
```

Observed address:

```text
0x9b1b0
```

Before installing the hooks, the module checks whether the private server is reachable.

The connectivity check is performed by:

```text
surveiller
```

Observed address:

```text
0x9b384
```

Target:

```text
88.96.61.105:4530
```

A flag around:

```text
0xc96f8
```

is set to `1` when the private server is reachable, otherwise `0`.

If unavailable, the module falls back to the original Photon Cloud behavior.

---

## 11. Photon Classes and Methods

`eu_installer` resolves:

```text
PhotonNetwork
FuturePlay.GameSettings
```

Important cached pointers:

```text
0xc96c0 = PhotonNetwork class
0xc96c8 = FuturePlay.GameSettings class
0xc96d0 = PhotonNetwork.ConnectToMaster
0xc96d8 = PhotonNetwork.SwitchToProtocol
0xc96e0 = GameSettings.get_PhotonGameVersion
0xc96e8 = ConnectToRegion original
0xc96f0 = ConnectToRegionMaster original
```

---

## 12. Photon Hooks

Two connection paths are intercepted.

### `PhotonNetwork.ConnectToRegion`

The original function is saved in:

```text
connect_region_origine
```

The hook checks the relevant region argument and whether the private server is reachable.

If the conditions are met, it calls:

```text
vers_eu(...)
```

Otherwise it jumps to the original trampoline.

### `NetworkingPeer.ConnectToRegionMaster`

The original function is saved around:

```text
0xc96f0
```

The same private-server availability logic is applied.

---

## 13. `vers_eu` — Actual Redirect

The actual redirect function is:

```text
vers_eu
```

Observed address:

```text
0x9b588
```

Sequence:

```text
PhotonNetwork.PhotonServerSettings.AppID
                |
                v
        get_PhotonGameVersion()
                |
                v
        SwitchToProtocol(TCP)
                |
                v
ConnectToMaster("88.96.61.105", 4530, AppID, version)
```

The module logs information equivalent to:

```text
eu : region eu -> serveur maison %s:%d (version %s)
```

The observed Photon AppID is:

```text
1000000000-b5e8-469d-a229-6b2e91ce1aa5
```

The AppID is not replaced by the native module.

---

## 14. Photon Protocol

The redirect explicitly calls:

```text
PhotonNetwork.SwitchToProtocol
```

with:

```text
ConnectProtocol = 1
```

The private connection therefore uses:

```text
TCP
port 4530
```

An original configuration may contain port `5055`, but the runtime redirect explicitly connects to:

```text
88.96.61.105:4530
```

---

## 15. Photon Authentication

The native module does not appear to manually construct the Photon authentication token.

The normal client flow is retained.

The PlayFab-compatible backend implements:

```text
GetPhotonAuthenticationToken
```

and returns a JWT-like token containing fields such as:

```json
{
  "pfid": "...",
  "app": "1000000000-b5e8-469d-a229-6b2e91ce1aa5",
  "exp": "..."
}
```

The normal Photon client then uses this authentication information.

Therefore:

```text
PlayFab-compatible backend
          |
          v
GetPhotonAuthenticationToken
          |
          v
Photon authentication
          |
          v
Private Photon server
```

---

## 16. Quantum

Quantum remains part of the original game architecture.

The Reborn module does not replace the original gameplay simulation.

The important distinction is:

```text
Photon
  |
  v
network transport / room
  |
  v
original Battlelands gameplay
  |
  v
original deterministic simulation
```

The Reborn modifications primarily affect connectivity and additional features.

---

## 17. Private Backend

Observed backend hostname:

```text
https://b.88-96-61-105.sslip.io
```

Server IP:

```text
88.96.61.105
```

Observed infrastructure:

```text
Caddy
MongoDB
custom REST API
```

The backend uses a cloned PlayFab title configuration.

Observed title ID:

```text
299E
```

---

## 18. Public Backend Routes

Observed public routes:

```text
GET  /
GET  /health
GET  /logo.png

POST /Client/GetTitleData
POST /Client/GetTitleNews
POST /Client/GetTime
POST /Client/LoginWithCustomID
```

---

## 19. Authenticated PlayFab-Compatible Routes

Observed routes include:

```text
GetUserInventory
GetCatalogItems
GetPlayerStatistics
GetFriendsList
GetPlayerSegments
GetUserData
UpdateUserData
GetLeaderboard
GetPhotonAuthenticationToken
Matchmake
GetCurrentGames
StartGame
```

The catalog route uses:

```json
{
  "CatalogVersion": "SeasonItems_14"
}
```

Player statistics include values such as:

```text
Wins
SeasonWins
NameChanges
XP
```

---

## 20. Matchmaking

The backend implements:

```text
Matchmake
GetCurrentGames
StartGame
```

However, actual room establishment is handled through Photon.

`Matchmake` can return:

```json
{
  "Status": "Waiting"
}
```

`StartGame` does not necessarily need to provide a traditional PlayFab server address.

This means a minimal implementation does not need to reproduce the entire original PlayFab matchmaking infrastructure.

---

## 21. CloudScript

The backend exposes:

```text
/Client/ExecuteCloudScript
```

Global metadata lists 25 client-called functions.

24 were implemented by the Reborn backend.

The unimplemented function observed was:

```text
saveS5nowTicks
```

Implemented functions include:

```text
addFriend
buyBattlePass
claimBattlePassReward
claimChallengeReward
claimDailyFreeItemReward
claimMatchReportRewards
claimTrophyRoadReward
consumeConsumable
deliverDynamicBundleS5
deliverEventRewardsS5
deliverSeasonalBundleS5
updateMatchTokenData
getSupportData
initializeDataS5
levelUpSkin
openMatchBox
prepareNameChange
purchaseBattlePoints
purchaseChest
purchaseConsumablePack
purchaseDoubleMatchBoxTokensBooster
refillDogTags
respondToFriendRequest
saveMatchCount
```

---

## 22. Important CloudScript Functions

### `getSupportData`

Returns profile/support information including:

```text
profile
statistics
currencies
inventory
friendCode
```

### `initializeDataS5`

Returns initialization/catalog data used by the client.

These functions are particularly relevant to getting the original client through its initialization phase.

---

## 23. Reborn-Specific Routes

Clan routes:

```text
/Client/Clan/Etat
/Client/Clan/Invitations
/Client/Clan/Classement
/Client/Clan/Creer
/Client/Clan/Inviter
/Client/Clan/Rejoindre
/Client/Clan/Quitter
/Client/Clan/Exclure
/Client/Clan/Rang
```

Nickname routes:

```text
/Client/Pseudo/Etat
/Client/Pseudo/Choisir
/Client/Pseudo/Effets
```

Other routes:

```text
/Client/Skin
/Client/Carte
/Client/Amis/Demandes
```

Tournament routes:

```text
/Client/Tournoi/Etat
/Client/Tournoi/Inscrire
/Client/Tournoi/Rejoindre
/Client/Tournoi/Quitter
/Client/Tournoi/Pret
/Client/Tournoi/Resultat
/Client/Tournoi/Salon
```

These are additional Reborn functionality and are not required for the minimal preservation architecture.

---

## 24. Reborn Extra Features

Additional features include:

```text
clans
custom animated nicknames
tournaments
custom maps
custom game modes
custom UI
```

Examples of custom modes:

```text
BazookaParty
BeachFight
CampersParadise
Heavyweight
HotDrop
Legendary
SaloonShowdown
SniperFest
SupplyRush
```

A rules system named:

```text
BLRRegles
```

contains parameters related to:

```text
speed
armor
crates
ammo
parachute
zone damage
zone speed
revive
weapon whitelist
weapon blacklist
```

These features are optional for an independent preservation server.

---

## 25. Reborn Network Flow

The complete network flow is:

```text
Battlelands client
       |
       v
PlayFab-compatible backend
       |
       +-- Login
       +-- player data
       +-- catalog
       +-- inventory
       +-- CloudScript
       +-- GetPhotonAuthenticationToken
       |
       v
Photon authentication
       |
       v
Native Photon redirect
       |
       v
88.96.61.105:4530
       |
       v
Private Photon server
       |
       v
Original game rooms
       |
       v
Original gameplay / Quantum
```

---

## 26. Minimum Architecture Required for V1

The Reborn implementation demonstrates that a full rewrite is unnecessary.

The minimum target is:

```text
Original Battlelands 2.9.6 client
             |
             v
Minimal PlayFab-compatible backend
             |
             +-- Login
             +-- player data
             +-- catalog
             +-- inventory
             +-- CloudScript
             +-- GetPhotonAuthenticationToken
                         |
                         v
                Photon authentication
                         |
                         v
               Small native redirect
                         |
                         v
                  Private Photon
                         |
                         v
                 Original gameplay
```

---

## 27. What Is Not Required for V1

Not initially required:

```text
clans
tournaments
custom maps
custom game modes
custom nickname effects
custom UI
Reborn-specific rules editor
all Reborn CloudScript functions
```

The first objective should simply be:

```text
login
  |
  v
player initialization
  |
  v
Photon authentication
  |
  v
private Photon connection
  |
  v
room
  |
  v
original gameplay
```

---

## 28. Original Project Status Before Reborn Discovery

The original client investigation reached a loop around:

```text
CheckAndUpdateSeason.MoveNext()
```

Observed sequence:

```text
LoginWithAndroidDeviceID
        |
        v
ExecuteCloudScript("startSeason14")
        |
        v
OnPlayFabLogin
        |
        v
Login again
        |
        v
ExecuteCloudScript
        |
        v
repeat
```

The original investigation patched:

```text
OnPlayFabLogin
_OnPlayFabLogin
```

to populate authentication state directly.

This removed an observed null-reference crash but did not reach Photon.

Other experiments included:

```text
blocking LoginWithAndroidDeviceID
modifying ExecuteCloudScript fields
returning errors
redirecting callback delegates
```

These did not produce a stable Photon path.

---

## 29. New Direction

The Reborn discovery changes the priority of the investigation.

Instead of spending additional effort trying to reproduce every detail of the original Futureplay backend, the next objective should be to reproduce the architecture demonstrated by Reborn.

Priority:

```text
1. Understand the Photon redirect
2. Build a minimal PlayFab-compatible backend
3. Generate valid Photon authentication
4. Connect to a private Photon server
5. Keep original Quantum/gameplay untouched
```

The `CheckAndUpdateSeason` loop should not be the central focus of the next implementation phase.

---

## 30. Recommended Client-Side Task

First reproduce the Photon redirect independently of the final server.

Investigate:

```text
JNI_OnLoad
attendre_il2cpp
IL2CPP reflection
eu_installer
surveiller
detourner
PhotonNetwork.ConnectToRegion
NetworkingPeer.ConnectToRegionMaster
PhotonNetwork.SwitchToProtocol
PhotonNetwork.ConnectToMaster
PhotonServerSettings.AppID
GameSettings.get_PhotonGameVersion
```

First milestone:

```text
load original libmain
        |
        v
wait for IL2CPP
        |
        v
resolve PhotonNetwork
        |
        +-- log AppID
        +-- log GameVersion
        +-- log connection calls
```

Only after this works should the actual redirect be enabled.

---

## 31. Recommended Backend Task

Initially implement only the endpoints required to reach Photon.

Priority candidates:

```text
POST /Client/LoginWithCustomID
POST /Client/GetTitleData
POST /Client/GetTime
POST /Client/GetCatalogItems
POST /Client/GetUserInventory
POST /Client/GetUserData
POST /Client/GetPlayerStatistics
POST /Client/ExecuteCloudScript
POST /Client/GetPhotonAuthenticationToken
```

The exact required set should be determined from runtime traffic rather than blindly reproducing the complete Reborn API.

---

## 32. Recommended Photon Task

First Photon milestone:

```text
Private Photon server
        |
        v
accept Battlelands AppID
        |
        v
accept Photon authentication
        |
        v
accept GameVersion
        |
        v
accept TCP connection on 4530
```

The private server should be independent of the Reborn production infrastructure.

Target:

```text
Original Battlelands client
        +
our PlayFab-compatible backend
        +
our Photon server
```

No dependency on:

```text
Reborn production backend
Reborn production Photon server
Reborn admin interface
```

---

## 33. Final Architecture

The resulting V1 architecture is:

```text
                   +----------------------+
                   | Battlelands 2.9.6   |
                   | Original Client     |
                   +----------+-----------+
                              |
                              v
                   +----------------------+
                   | Minimal native patch |
                   | Photon redirect      |
                   +----------+-----------+
                              |
                 +------------+------------+
                 |                         |
                 v                         v
       +------------------+     +------------------+
       | PlayFab clone    |     | Private Photon   |
       | HTTP / JSON      |     | TCP              |
       +---------+--------+     +---------+--------+
                 |                        |
                 |                        v
                 |                Original game rooms
                 |                        |
                 +------------------------+
                                          |
                                          v
                               Original gameplay / Quantum
```

---

## 34. Final Conclusion

The most important finding from Battlelands Reborn is:

> **The original Battlelands client already contains almost everything required to run the game again.**

The original client contains:

```text
Unity
IL2CPP
Quantum
gameplay
assets
Photon client
PlayFab client
```

The external services can be replaced.

The minimum modification appears to be a native Photon redirect that changes:

```text
Photon Cloud / region resolution
```

into:

```text
Private Photon server
```

while preserving:

```text
AppID
GameVersion
Photon authentication
original Photon client
original gameplay
```

Therefore the primary preservation target is:

```text
Original Battlelands 2.9.6
        +
minimal PlayFab-compatible backend
        +
minimal Photon redirect
        +
private Photon server
        =
independent Battlelands instance
```

Reborn-specific features can be considered optional future work.
