# SERVER_REQUIREMENTS.md

## Battlelands Royale v2.9.6 — Private Server Requirements

Based on evidence extracted from the client APK, a private server for Battlelands Royale must implement or emulate the following services.

---

## 1. PlayFab-Compatible API Server (Critical)

The client makes all backend calls to PlayFab. A private server MUST implement a PlayFab-compatible HTTP API.

### 1.1 Authentication Endpoints

| Endpoint | Usage | Request | Response |
|---|---|---|---|
| `/Client/LoginWithCustomID` | Device-based login | `{"CustomId": "...", "TitleId": "..."}` | `SessionTicket`, `PlayFabId`, `EntityToken` |
| `/Client/LoginWithFacebook` | Facebook login | `{"AccessToken": "...", "TitleId": "..."}` | `SessionTicket`, `PlayFabId` |
| `/Client/LoginWithAndroidDeviceID` | Android device ID login | (likely fallback) | SessionTicket |
| `/Client/LinkCustomID` | Link device to account | `{"CustomId": "...", "ForceLink": true}` | (empty) |
| `/Client/GetPhotonAuthenticationToken` | Photon auth token | (empty) | `{"PhotonAuthenticationToken": {"Token": "..."}}` |

### 1.2 Player Data Endpoints

| Endpoint | Usage |
|---|---|
| `/Client/GetUserReadOnlyData` | Read player data keys |
| `/Client/GetUserData` | Read/write player data |
| `/Client/UpdateUserData` | Write player data |
| `/Client/GetUserInventory` | Get player items |
| `/Client/GetCatalogItems` | Get item catalog |
| `/Client/GetStoreItems` | Get store offers |
| `/Client/PurchaseItem` | Purchase item |
| `/Client/ConfirmPurchase` | Confirm purchase |
| `/Client/ConsumeItem` | Consume consumable |
| `/Client/GetAccountInfo` | Get player account info |
| `/Client/GetPlayerProfile` | Get player profile |
| `/Client/GetPlayerStatistics` | Get stats |
| `/Client/UpdatePlayerStatistics` | Update stats |
| `/Client/GetLeaderboard` | Get global leaderboard |
| `/Client/GetFriendLeaderboard` | Get friends leaderboard |
| `/Client/GetFriendLeaderboardAroundPlayer` | Get leaderboard around player |
| `/Client/AddFriend` | Add friend |
| `/Client/RemoveFriend` | Remove friend |
| `/Client/GetFriendsList` | Get friends list |
| `/Client/ExecuteCloudScript` | Execute cloud script function |
| `/Client/GetTitleData` | Get title global data |
| `/Client/GetTitleNews` | Get title news |

### 1.3 Required Data Keys (Player Read-Only Data)

The client reads these keys via `GetUserReadOnlyData` after login:

| Key | Content Type | Purpose |
|---|---|---|
| `InboxMessageStates` | JSON | Message/states inbox |
| `BaseGameTutorial` | JSON | Tutorial completion state |
| `MatchBoxTokenData` | JSON | Match box tokens earned/used |
| `TrophyRewardsData` | JSON | Trophy road progress |
| `ConsumableInventory` | JSON | Consumable items (pickaxe, tags) |
| `SkinInventory` | JSON | Owned skins |
| `SkinUsageCounts` | JSON | Usage stats per skin |
| `SeasonStatsHistory` | JSON | Per-season stats |
| `UnlockedAltSkins` | JSON | Alternate skin unlocks |
| `BattlePointsPacks` | JSON | Purchased battle points packs |
| `initializeDataS5` | JSON | Season 5 initialization data |
| `getSupportData` | ? | Support/account data |

### 1.4 Player Data Saves

The client writes these keys:
- `saveMatchCount` — match count persistence
- `saveS5nowTicks` — season 5 time data
- `updateMatchTokenData` — match box token updates
- `claimMatchReportRewards` — post-match reward claiming
- `claimTrophyRoadReward` — trophy road claim
- `claimBattlePassReward` — battle pass claim
- `claimChallengeReward` — challenge claim
- `claimDailyFreeItemReward` — daily free item claim
- `consumeConsumable` — consume an item
- `levelUpSkin` — level up a skin
- `setPlayerStatistics` — update player stats

### 1.5 Title Data Keys (Global Read-Only Data)

Firebase Remote Config keys that may also exist as PlayFab title data:
- `ProtocolServerPort` — Photon server port override
- `BoxTokenRefreshIntervalSeconds` — token refresh rate
- `DisableCloudScriptEvents` — toggle for CS events
- `XPBTSeasonEndTimes` — season end timestamps
- `SessionId` — current session ID
- `MatchBoxTokenBooster` — Token booster amounts
- `DynamicBundleOffer.*` — Dynamic shop offers

---

## 2. Photon-Compatible Game Server (Critical)

The client connects to Photon Cloud for real-time multiplayer. A private server must implement a Photon-compatible relay/server.

### 2.1 Transport
- **Primary**: WebSocket Secure (`wss://`) — `ExitGames.Client.Photon.SocketWebTcp`
- **Auth Mode**: `AuthOnceWss` (authenticate once over WebSocket)
- **Fallback**: UDP with DatagramEncryption (`Expected protocol set to UDP, due to encryption mode DatagramEncryption`)
- **NameServer**: default (configurable in `PhotonServerSettings`)

### 2.2 Operations Used
| Operation | Description |
|---|---|
| `OpAuthenticate` | With PlayFab token |
| `OpJoinLobby` | Join matchmaking lobby |
| `OpLeaveLobby` | Leave lobby |
| `OpCreateRoom` | Create game room |
| `OpJoinRoom` | Join existing room |
| `OpJoinRandomRoom` | Join random (auto-match) |
| `OpLeaveRoom` | Leave room |
| `OpGetGameList` | Get game list (SqlLobby) |
| `OpRaiseEvent` | Send game events (RPCs) |
| `OpSetPropertiesOfActor` | Set actor properties |
| `OpSetPropertiesOfRoom` | Set room properties |
| `OpChangeGroups` | Change interest groups |
| `OpWebRpc` | Web RPC calls |

### 2.3 Custom Properties Observed
- Room properties: `levelId` (int/string), GameMode (Solo/Duo/Squad)
- Actor properties: Player ID, Loadout, Skin, Team
- Lobby types: DefaultLobby, SqlLobby

### 2.4 Quantum Deterministic Lockstep
The game uses Quantum ECS on top of Photon for deterministic simulation:
- `QuantumGame`, `QuantumRunner`
- `DeterministicSessionConfig` (from `PhotonDeterministic.dll`)
- Frame-based input recording + replay
- NavMesh baking (`Baking Quantum NavMesh '{0}' complete`)
- Custom physics layers from `SimulationConfig`

---

## 3. Minimal Server Implementation

For a minimal functional private server, implement:

### 3.1 Must Have
```
1. PlayFab-compatible HTTP API server
   - LoginWithCustomID endpoint (returns SessionTicket, PlayFabId)
   - GetPhotonAuthenticationToken (returns a token)
   - GetUserReadOnlyData (returns empty data for all keys)
   
2. Photon-compatible game server (WebSocket)
   - NameServer (host list)
   - Master Server (lobby + matchmaking)
   - Game Server (room relay, even without game logic)
```

### 3.2 Nice to Have
```
3. Firebase Remote Config-compatible endpoint
   - Returns default values for all config keys
   
4. PlayFab data storage stubs
   - Read/write user data keys
   - Inventory/catalog management
```

### 3.3 Not Needed Initially
```
- Facebook SDK validation
- AdMob/Unity Ads/Audience Network
- Unity IAP/UDP receipt validation
- Firebase Analytics
- CloudScript execution
- Real leaderboard logic
```

---

## 4. Identified Identifiers

| Key | Value | Location |
|---|---|---|
| Package | `com.futureplay.battleground` | AndroidManifest |
| App Version | 2.9.6 (code 668) | AndroidManifest |
| Unity Version | 2018.4.31f1 | globalgamemanagers |
| IL2CPP Metadata | v24 | global-metadata.dat |
| PlayFab SDK | UnitySDK-2.66.190509 | Metadata strings |
| Facebook App ID | 529204907466874 | strings / AndroidManifest |
| AdMob App ID | ca-app-pub-7178055090700599~6226408259 | Metadata strings |
| Unity Build ID | 34160d74-7cbb-4d1e-b3a0-a9355ccac61b | Metadata strings |
| Photon AppId | `bcf1bfc88d9114a88a8e0b503ef655cc` | globalgamemanagers |
| Photon AppId | `48f79e6d-4c67-4b5a-a4b5-c6d4216ea4cc` | globalgamemanagers (secondary) |
| Futureplay ID | `futureplay-1375e635-a30a-4958-9529-6a97436d4f86` | globalgamemanagers |
| PlayFab TitleId | *(stored in PlayFabSharedSettings, not found as plaintext)* | — |

---

## 5. Implementation Notes

### 5.1 Photon Token Generation
The PlayFab `GetPhotonAuthenticationToken` returns a JWT-like token. For a private server, any opaque token string is sufficient — the Photon server just needs to accept it.

### 5.2 Session Management
The client stores:
- `customid.txt` — the CustomId used for LoginWithCustomID (Android device ID + hash)
- `pfid.txt` — the PlayFabId received from login
- SessionTicket is kept in memory for subsequent API calls

### 5.3 Auth Header
All PlayFab API calls include:
```
X-Authorization: <SessionTicket>
X-PlayFabSDK: UnitySDK-2.66.190509
Content-Type: application/json
```

### 5.4 Config Override Flow
```
Firebase Remote Config values
       ↓
ConfigLoader.OverrideCacheWithFirebaseConfigs
       ↓
"Override configs and restart game"  ← if incompatible
```

### 5.5 Photon Connection Flow
```
PlayFab.GetPhotonAuthenticationToken
       ↓
PhotonNetwork.ConnectToNameServer()
       ↓
Call ConnectToNameServer to ping available regions.
       ↓
AvailableRegions received
       ↓
Connected to masterserver.
       ↓
OpJoinLobby()
       ↓
OpCreateRoom / OpJoinRandomRoom / OpJoinRoom
```
