# Architecture générale

## Vue d'ensemble

```
┌──────────────────────────────────────────────────────────┐
│                    Client (Unity/Android)                 │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │            Quantum Framework (Futureplay)           │  │
│  │  ┌─────────┐ ┌──────────┐ ┌─────────────────────┐  │  │
│  │  │  Core   │ │  State   │ │      Systems        │  │  │
│  │  │  (ECS)  │ │ (Game    │ │  Actor, Combat,     │  │  │
│  │  │         │ │  State)  │ │  Movement, Weapon,  │  │  │
│  │  └─────────┘ └──────────┘ │  Pickup, AreaEffect  │  │  │
│  │                           └─────────────────────┘  │  │
│  └────────────────────────────────────────────────────┘  │
│                          │                                │
│  ┌────────────────────────────────────────────────────┐  │
│  │         Photon PUN (Real-time Networking)           │  │
│  │  ┌────────────────┐ ┌──────────────────────────┐   │  │
│  │  │ LoadBalancing  │ │  QuantumNetworkCommu-   │   │  │
│  │  │    Peer        │ │  nicator (custom)        │   │  │
│  │  └────────────────┘ └──────────────────────────┘   │  │
│  └────────────────────────────────────────────────────┘  │
│                          │                                │
│  ┌────────────────────────────────────────────────────┐  │
│  │   PlayFab SDK (REST + JSON)                        │  │
│  │   Auth, Player Data, Catalog, Inventory,           │  │
│  │   Leaderboard, Matchmaking                         │  │
│  └────────────────────────────────────────────────────┘  │
│                          │                                │
│  ┌────────────────────────────────────────────────────┐  │
│  │   Firebase (Analytics, Remote Config, Auth)        │  │
│  │   Facebook SDK (Login, Social, Ads)                │  │
│  │   AdMob / Unity Ads / Audience Network (Ads)       │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
         │                        │
         ▼                        ▼
┌──────────────────┐  ┌──────────────────────────┐
│   PlayFab API    │  │  Photon Cloud            │
│   *.playfabapi   │  │  *.exitgames.com         │
│   .com           │  │  (ws:// / wss://)        │
│   (HTTPS/JSON)   │  │  (TCP/WebSocket)         │
└──────────────────┘  └──────────────────────────┘
```

## Structure du projet Unity

Basé sur les chemins d'assets découverts via les chaînes IL2CPP :

```
Assets/
├── Quantum/
│   ├── Assets/
│   │   ├── AreaEffectData/
│   │   ├── BuildingData/
│   │   ├── ConsumableData/
│   │   ├── GameConfig
│   │   ├── Map/
│   │   ├── MapLocationData
│   │   ├── NavMeshAsset/
│   │   ├── PickupData/
│   │   ├── PickupListData
│   │   ├── ProjectileData/
│   │   ├── RingOfDeathData
│   │   ├── StatusEffectData/
│   │   ├── UserColliderData
│   │   ├── UserMapData
│   │   └── WeaponData/
│   ├── Configurations/
│   │   ├── Deterministic
│   │   ├── QuantumEditorSettings
│   │   └── SimulationConfig
│   └── Animator Graph
├── Futureplay/
│   └── TutorialConfig
├── Prefabs/
│   └── UI/
│       └── BattlePassCards
└── Spine/
```

## Flux de démarrage du jeu

1. Android lance `com.futureplay.FPAndroidDeeplinkPlayerActivity`
2. Unity s'initialise avec les plugins (Firebase, Facebook, etc.)
3. Firebase Remote Config récupère la configuration à distance
4. PlayFab : Login (via `LoginWithAndroidDeviceID`)
5. Chargement des données joueur (inventaire, skins, stats)
6. Récupération du catalogue IAP
7. Le joueur arrive dans le lobby
8. Matchmaking via PlayFab ou custom rooms
9. Photon se connecte au Photon Cloud pour la partie
10. Quantum gère la logique de jeu synchrone (déterministe)
