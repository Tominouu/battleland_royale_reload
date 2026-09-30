# Battlelands Royale - Analyse d'APK (v2.9.6)

## Informations générales

| Champ | Valeur |
|-------|--------|
| **Package** | `com.futureplay.battleground` |
| **Version** | 2.9.6 (code 668) |
| **Développeur** | Futureplay |
| **Min SDK** | 19 (Android 4.4) |
| **Target SDK** | 30 (Android 11) |
| **Moteur** | Unity 2018.4.31f1 (IL2CPP) |
| **Backend** | PlayFab + Photon (PUN) |
| **Taille APK** | ~120 MB (398 MB décompressé) |

## Documents

| Document | Description |
|----------|-------------|
| [01_engine_analysis.md](01_engine_analysis.md) | Analyse du moteur Unity et IL2CPP |
| [02_architecture.md](02_architecture.md) | Architecture générale du jeu |
| [03_network.md](03_network.md) | Analyse réseau complète |
| [04_endpoints.md](04_endpoints.md) | Liste des endpoints API |
| [05_authentication.md](05_authentication.md) | Système d'authentification |
| [06_matchmaking.md](06_matchmaking.md) | Système de matchmaking |
| [07_gameplay.md](07_gameplay.md) | Systèmes de gameplay |
| [08_serialization.md](08_serialization.md) | Formats de sérialisation |
| [09_configuration.md](09_configuration.md) | Configuration et clés |
| [10_classes.md](10_classes.md) | Classes importantes |
| [11_diagram.md](11_diagram.md) | Diagramme d'architecture |
| [12_REBORN_ANALYSIS.md](12_REBORN_ANALYSIS.md) | Analyse de l'APK Battlelands Reborn |
| [13_MINIMAL_REDIRECT.md](13_MINIMAL_REDIRECT.md) | Redirection minimale PlayFab + Photon (natif + métadonnées) |
| [14_REBORN_IL2CPP_PATCHES.md](14_REBORN_IL2CPP_PATCHES.md) | Les 13 patchs Reborn de libil2cpp.so + cause du blocage à 1 % |
| [15_PLAYFAB_LOGIN.md](15_PLAYFAB_LOGIN.md) | Premier login PlayFab depuis Waydroid (URL, TLS/overlay, LoginWithAndroidDeviceID, appels suivants) |
