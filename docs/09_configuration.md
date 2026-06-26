# Configuration et clés

## Clés trouvées

### Facebook

| Clé | Valeur |
|-----|--------|
| Facebook App ID | `529204907466874` |
| Facebook Scheme | `battlelands://` |
| SDK Version | `11.0.0` (dans FB.Init) |

### Google

| Clé | Valeur |
|-----|--------|
| AdMob App ID | `ca-app-pub-7178055090700599~6226408259` |
| Play Billing Version | `3.0.3` |

### Unity

| Clé | Valeur |
|-----|--------|
| Build ID | `34160d74-7cbb-4d1e-b3a0-a9355ccac61b` |
| Unity Version | `2018.4.31f1` |
| PlayFab SDK | `UnitySDK-2.66.190509` |

### Firebase

| Clé | Valeur |
|-----|--------|
| Firebase C++ SDK | `6.12.0` |
| Services | Analytics, Remote Config, Instance ID, Auth |

## IAP Product IDs

Basé sur les références trouvées :

```
com.futureplay.battleground.battlebucks
com.futureplay.battleground.bpoffer
com.futureplay.battleground.bundle
com.futureplay.battleground.bundles
com.futureplay.battleground.gems
```

## PlayFab Title ID

Le PlayFab Title ID est configuré via `PlayFabSharedSettings` dans l'éditeur Unity. Il n'a pas pu être déterminé précisément par analyse statique seule (stocké dans les assets Unity, pas dans une chaîne lisible).

**Non déterminé :** Le Title ID PlayFab exact.

## Photon App ID

Similaire au PlayFab Title ID, le Photon App ID est configuré via les PlayFabSharedSettings et n'a pas été trouvé comme chaîne lisible.

**Non déterminé :** Le Photon App ID exact.

## Configuration Firebase

Le fichier `google-services.json` n'a pas été trouvé dans l'APK (probablement intégré dans les ressources Unity). Les services Firebase suivants sont activés :
- Analytics
- Remote Config
- Instance ID
- Auth

## Remote Config Keys

Basé sur les noms de clés utilisés dans le code :

```
Override configs and restart game
BoxTokenRefreshIntervalSeconds
DisableCloudScriptEvents
ProtocolServerPort
```

## Paramètres de déterminisme Quantum

Le jeu utilise :
- `Quantum/Configurations/Deterministic` - Configuration déterministe
- `Quantum/Configurations/SimulationConfig` - Simulation
- `Quantum/Configurations/QuantumEditorSettings` - Editor settings
- `Futureplay/TutorialConfig` - Tutoriel

## Deep links

```
Scheme: blr://
  - blr://inviteFriend/
  - blr://customBattle/
```

## Services Firebase

```
metrics_collection_deactivated
clear_old_logs
analytics
auth
crashlytics
database
dynamic_links
functions
instance_id
invites
messaging
performance
remote_config
storage
test_lab
```
