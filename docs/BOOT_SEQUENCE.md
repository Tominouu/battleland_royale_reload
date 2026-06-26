# BOOT_SEQUENCE.md

## Battlelands Royale v2.9.6 — Client Boot Sequence

This document traces the exact startup flow of the game client from launch to gameplay, based on evidence extracted from `global-metadata.dat` (IL2CPP string heap), `libil2cpp.so` (runtime strings), and `globalgamemanagers` (Unity player settings).

---

## Phase 0: Native / Unity Engine Init

1. **Android Activity: `com.futureplay.battleground.unityactivity`** (or UnityPlayerActivity)
   - Launched by Android OS
   - Loads `libunity.so` → `libil2cpp.so`
2. **Unity Engine init** (`boot.config`)
   - `gfx-enable-native-gfx-jobs=1`
   - `scripting-runtime-version=latest`
   - `wait-for-native-debugger=0`
3. **IL2CPP runtime init**
   - `il2cpp_init`, `il2cpp_runtime_class_init`, `il2cpp_runtime_object_init`
4. **First scene load** — likely `Initialization` or `Boot` scene
   - `GetSceneManager().DontDestroyOnLoad` (persistent objects)

---

## Phase 1: SDK Initialization

### 1.1 Firebase Init
```
FirebaseInitializationException
Firebase.RemoteConfig
```
- `FirebaseApp` initializes (likely from `google-services.json` bundled in APK)
- `Firebase.RemoteConfig.Fetch` called

### 1.2 Facebook SDK Init
```
Facebook.Unity
fb_mobile_content_view
```
- FB SDK init with App ID `529204907466874`

### 1.3 Ads SDK Init
```
GoogleMobileAds.Api
GoogleMobileAds.Android
AdMobAdsAppId -> ca-app-pub-7178055090700599~6226408259
AudienceNetwork.Utility
```
- AdMob init with App ID
- Facebook Audience Network init

### 1.4 Unity IAP Init
```
UnityEngine.Purchasing
UnityEngine.UDP
IAPProductCatalog
```
- Initialize Unity IAP / UDP
- Fetch IAP catalog from store

### 1.5 Analytics Init
```
Firebase.Analytics
AppsFlyer (AppsFlyerAppId)
```

---

## Phase 2: Config Loading

### 2.1 Local Config Load
```
ConfigLoader
```
- Load local config from `Resources/` assets
- `RuntimeConfig`, `GameConfig`, `SimulationConfig`, `TutorialConfig`, `BootConfig`

### 2.2 Firebase Remote Config Fetch
```
ConfigLoader.FetchFirebaseConfigs    (coroutine state machine: FetchFirebaseConfigs_d__6)
ConfigLoader.FetchFirebaseConfigs FirebaseException
ConfigLoader.OverrideCacheWithFirebaseConfigs
```
- Fetch Firebase Remote Config
- Override local config with Firebase values
- Keys found in Remote Config:
  - `ProtocolServerPort`
  - `BoxTokenRefreshIntervalSeconds`
  - `DisableCloudScriptEvents`
  - `XPBTSeasonEndTimes`
  - `SessionId`

### 2.3 Config Validation
```
Override configs and restart game
```
- If configs indicate version mismatch, game restarts

---

## Phase 3: PlayFab Authentication

### 3.1 Set Title ID
```
PlayFabSharedSettings
PlayFabSettings.TitleId
```
- TitleId loaded from `PlayFabSharedSettings` ScriptableObject asset
- Default Endpoint: `https://<TitleId>.playfabapi.com`

### 3.2 Device ID Setup
```
customid.txt  -> /customid.txt
pfid.txt      -> /pfid.txt
getContentResolver
android.provider.Settings$Secure.getString -> android_id
```
- Generate/restore custom device ID from file storage
- Android Advertising ID (if available)

### 3.3 Login
```
PlayfabService.LoginAndLoadData
PlayfabService - LoginAndLoadData Error : 299E
```
**Authentication flow:**
1. Try `LoginWithCustomID` with device ID (or `LoginWithFacebook` if FB linked)
   - Endpoint: `https://<TitleId>.playfabapi.com/Client/LoginWithCustomID`
   - Response: `SessionTicket`, `PlayFabId`
2. If first-time login → `CreateAccount` (via `CreateAccountInfoRequestParameters`)
3. Force-link: `LinkCustomID` → `https://<TitleId>.playfabapi.com/Client/LinkCustomID`
4. Save: `customid.txt` (custom ID), `pfid.txt` (PlayFab ID)

### 3.4 Load Player Data
```
PlayfabService.LoginAndLoadData
```
After login, fetch these data keys (via `GetUserReadOnlyData`):
- `InboxMessageStates` — message inbox
- `BaseGameTutorial` — tutorial progress
- `MatchBoxTokenData` — match box tokens
- `TrophyRewardsData` — trophy road rewards
- `ConsumableInventory` — consumable items
- `SkinInventory` — skin ownership
- `SkinUsageCounts` — usage statistics
- `SeasonStatsHistory` — season statistics
- `UnlockedAltSkins` — alternate skins
- `BattlePointsPacks` — BP purchases
- `LevelUp` — level data
- `initializeDataS5` — season 5 init data

Also fetch catalog (`GetCatalogItems`) and user inventory (`GetUserInventory`):
```
Fetched catalog
Error parsing IAP catalog
Failed to fetch IAP catalog, using cache
```

---

## Phase 4: Photon Token & Connect

### 4.1 Get Photon Token
```
GetPhotonAuthenticationToken
```
- Call PlayFab: `https://<TitleId>.playfabapi.com/Client/GetPhotonAuthenticationToken`
- Response contains: `PhotonAuthenticationToken`

### 4.2 Configure Photon
```
PhotonServerSettings
PhotonApplicationId
Protocol:       WebSocket (ws://, wss://)
AuthMode:       AuthOnceWss
NameServer:     ns0.exitgames.com (default)
```
- Photon AppId loaded from `PhotonServerSettings` ScriptableObject
- Protocol set to WebSocket (with fallback to UDP for DatagramEncryption)

### 4.3 Connect to Photon NameServer
```
Call ConnectToNameServer to ping available regions.
Waiting for AvailableRegions. State:
PhotonNetwork.networkingPeer.AvailableRegions
No regions available. Are you sure your appid is valid and setup?
```
- Connect to `ns0.exitgames.com` via WebSocket
- Fetch available regions list
- Log: region addresses + ping times

### 4.4 Connect to Master Server
```
Connected to NameServer.
Connected to masterserver.
```
- Select best region by ping
- Authenticate with Photon using token from PlayFab
- Set `NickName`, `UserID`

### 4.5 Join Lobby
```
OpJoinLobby()
LobbyController
lobby '{0}'[{1}] rooms: {2} players: {3}
```
- Join Photon Lobby
- LobbyController handles lobby state

---

## Phase 5: Main Menu / Lobby

### 5.1 Lobby Data Load
```
LobbyTest exceeded Timeout value of {0}ms
```
- Timeout monitor for lobby loading

### 5.2 UI Initialization
UI components found:
- `UIMainMenu`, `UIBoxShop`, `UIBattlebucksShopItem`
- `SkinShop`, `UICustomRoom`, `UICustomizationSlot`
- `MatchReportPopup`, `TokenBoostPopup`, `DogTagPopup`
- Various battle pass, chest, event popups

### 5.3 Matchmaking
```
OpCreateRoom()
OpJoinRandomRoom()
OpJoinRoom()
MatchBox.BoxCapAmountText hours
CustomBattle.GameModeChanged.Squad
CustomBattle.GameModeChanged.Duo
CustomBattle.GameModeChanged.Solo
```
- Matchmaking via Photon Lobby/Room system
- Custom Battle support (`CustomBattle.*` events):
  - `CustomBattle.PlayerJoined`
  - `CustomBattle.PlayerLeft`
  - `CustomBattle.LeaderChanged`
  - `CustomBattle.MaxPlayersChanged`
  - `CustomBattle.BotsEnabled` / `BotsDisabled`
  - `CustomBattle.RoomClosedError`, `RoomFullError`, `RoomNotFoundError`

---

## Phase 6: Game Start (Quantum ECS)

### 6.1 QuantumRunner Init
```
QuantumRunner
QuantumRunner: Starting Game
Not connected to photon
Can't start networked game when not in a room
```
- `QuantumRunner` is the main game loop orchestrator
- Checks Photon connection state before starting networked game

### 6.2 Room Join Setup
```
QuantumPlugin
LobbyRunner.JoinFailed:
QuantumPluginLobbyRunner.JoinFailed: 2fd21053-1cdf-4067-887c-b83edd1a1af4
LobbyController.OnPhotonJoinRoomFailed
```
- On room join: Map loaded, Quantum ECS initialized
- `QuantumRunnerLocalReplay`, `QuantumRunnerLocalSavegame` for debug modes
- Replay recording: `QuantumGame.ReplayTools: Input recording started`

### 6.3 Game Systems
Quantum systems based on string evidence:
- `Actor`, `ActorConfig`, `ActorBotSystem`, `ActorBuildingSystem`
- `DynamicProjectile`, `KinematicProjectile`, `Pickup`
- `NavMesh` baking
- `SimulationConfig` with physics layers

### 6.4 Game Over / Match Report
```
MatchReportPopup.BonusRewardsLeft
```
- Match report displayed
- Rewards claimed via PlayFab:
  - `claimMatchReportRewards`
  - `saveMatchCount`
  - `updateMatchTokenData`

---

## Phase 7: Periodic Background Operations

### 7.1 Token Refresh
```
BoxTokenRefreshIntervalSeconds
matchBoxSkipTimeWithGems
DoubleTokensAvailable
AvailableMatchBoxTokens
```
- Periodic match box token refresh timer

### 7.2 Firebase Config Refresh
```
ConfigLoader.FetchFirebaseConfigs
```
- Periodic refresh of Firebase Remote Config

### 7.3 PlayFab Data Sync
```
saveMatchCount
saveS5nowTicks
updatePlayerStatistics
```
- Periodic save of match stats, season data

---

## Network Architecture Summary

```
[Client]
  │
  ├── HTTPS ──── PlayFab API (playfabapi.com)
  │   │         SDK: UnitySDK-2.66.190509
  │   │         Auth: LoginWithCustomID / LoginWithFacebook
  │   │         Data: GetUserReadOnlyData, GetUserInventory
  │   │         Token: GetPhotonAuthenticationToken
  │   │
  ├── WSS ────── Photon Cloud (ns0.exitgames.com)
  │   │         AppId: <GUID from PhotonServerSettings>
  │   │         Transport: WebSocket (AuthOnceWss)
  │   │         Lobby → Room → Game
  │   │
  ├── HTTPS ──── Firebase Remote Config
  │   │         Config overrides, feature toggles
  │   │
  ├── HTTPS ──── Facebook Graph API
  │   │         /me/permissions, access token
  │   │
  └── HTTPS ──── Ad Networks (AdMob, Audience Network, Unity Ads)
```

## Key Classes (from metadata strings)

| Class | Role |
|---|---|
| `StartUp` | Game initialization handler |
| `ConfigLoader` | Loads config from Firebase + local cache |
| `PlayfabService` | PlayFab auth + data operations |
| `LobbyController` | Photon lobby management |
| `LobbyRunner` | Quantum lobby runner |
| `QuantumPlugin` | Plugin orchestrating Quantum + Photon |
| `QuantumRunner` | Deterministic game loop runner |
| `CustomBattle*` | Custom battle room management |
| `UICustomRoom` | Custom room creation UI |
| `MatchReportPopup` | Post-game rewards display |
| `MatchBox.*` | Match box/token system |
| `ClubRoyale.*` | Season pass system |
| `DynamicBundleContent.*` | Dynamic shop bundles |

## Firestore / Redis / MySQL

Not directly observed in client strings. The game uses:
- **PlayFab** for all user data persistence (titles, inventory, stats)
- **Photon** for real-time match state
- **Firebase** for Remote Config only
- No direct MySQL/Redis strings found in client

If a private server replaces all of these, it needs:
1. PlayFab-compatible API server (for auth, data, photon token)
2. Photon-compatible game server (for matchmaking + relay)
3. Firebase Remote Config-compatible endpoint (for config overrides)
