# Classes importantes

## Réseau

| Classe | Assembly | Rôle |
|--------|----------|------|
| `QuantumNetworkCommunicator` | Assembly-CSharp | Wrapper Photon LoadBalancingPeer |
| `LoadBalancingPeer` | Photon3Unity3D | Peer Photon |
| `ActorPhotonData` | Assembly-CSharp | Données Photon des acteurs |
| `ActorPhotonDataSerialize` | Assembly-CSharp | Sérialisation Photon |
| `ActorViewManager` | Assembly-CSharp | Gestionnaire vues acteurs |
| `ActorView` | Assembly-CSharp | Vue d'un acteur |
| `ActorViewAction` | Assembly-CSharp | Action visuelle |

## PlayFab / Services

| Classe | Rôle |
|--------|------|
| `PlayFabSharedSettings` | Configuration PlayFab |
| `PlayfabService` | Service PlayFab principal |
| `ConfigLoader` | Chargement de configuration |
| `AnalyticsService` | Service d'analytics |
| `AdService` | Service de publicité |
| `AdProvider` | Fournisseur de pub |
| `AdMobProvider` | Pub AdMob |
| `AdView` | Vue publicitaire |

## Quantum Core

| Classe | Rôle |
|--------|------|
| `QuantumGame` | Instance de jeu Quantum |
| `Frame` | Frame de simulation |
| `FrameSnapshot` | Capture d'état |
| `RuntimeConfig` | Configuration runtime |
| `RuntimePlayer` | Données runtime du joueur |
| `SystemSetup` | Configuration des systèmes |

## Game Config

| Classe | Rôle |
|--------|------|
| `GameConfig` | Configuration globale du jeu |
| `ActorConfig` | Configuration des acteurs |
| `AimAssistConfig` | Aide à la visée |
| `BuildingData` | Données construction |
| `MapLocationData` | Points carte |
| `UserMapData` | Données utilisateur carte|

## Données de jeu

| Classe | Rôle |
|--------|------|
| `SkinData` | Données de skin |
| `SkinShopData` | Données boutique skins |
| `RuntimePlayerData` | Données runtime joueur |
| `StartParameters` | Paramètres de démarrage |
| `SkinInventory` | Inventaire des skins |
| `ConsumableInventory` | Inventaire consommables |

## UI

| Classe | Rôle |
|--------|------|
| `MatchBoxPopup` | Popup boîte de match |
| `CustomBattleEntryPopup` | Popup entrée partie custom |
| `CustomBattlePopup` | Popup partie custom |
| `UIBoxShop` | Boutique de coffres |
| `UIBattlebucksShopItem` | Item boutique BattleBucks |
| `UICustomRoom` | Room personnalisée |
| `UICustomizationSlot` | Slot de personnalisation |

## Lobby / Social

| Classe | Rôle |
|--------|------|
| `Lobby` | Lobby |
| `ChatClient` | Client de chat Photon |
| `ChatPeer` | Peer de chat |

## Services externes

| Classe | Rôle |
|--------|------|
| `FacebookAPIService` | Service Facebook |
| `AppsFlyerService` | Service AppsFlyer |
| `AppUtils` | Utilitaires applicatifs |

## Non déterminé (avec forte probabilité)

Les classes suivantes sont fortement suspectées d'exister mais n'ont pas été confirmées directement :

| Classe suspectée | Raison |
|-----------------|--------|
| `APIClient` | Appel REST générique |
| `PacketHandler` | Gestion des paquets réseau |
| `MessageRouter` | Routage des messages |
| `PlayerManager` | Gestion des joueurs |
| `GameManager` | Gestion de partie |
| `WeaponController` | Contrôle des armes |
| `MatchManager` | Gestion du match |

> **Note :** Ces classes n'ont pas pu être confirmées car l'analyse complète de la table des symboles IL2CPP nécessite des outils comme Il2CppDumper, qui n'ont pas pu être installés dans cet environnement. L'analyse s'est basée sur l'extraction de chaînes de caractères du binaire natif.
