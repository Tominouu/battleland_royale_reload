# TODO — Prochaines étapes pour le serveur privé

## Priorité Haute

- [ ] **Déterminer le PlayFab Title ID** — extraire des données sérialisées de `PlayFabSharedSettings` dans `globalgamemanagers` (nécessite AssetStudio ou analyse binaire poussée)
- [ ] **Vérifier/déterminer le Photon App ID** — candidats trouvés : `bcf1bfc88d9114a88a8e0b503ef655cc`, `48f79e6d-4c67-4b5a-a4b5-c6d4216ea4cc`, `futureplay-1375e635-a30a-4958-9529-6a97436d4f86` (à confirmer)
- [ ] **Analyser le protocole Photon personnalisé (QuantumNetworkCommunicator)** — classes `LobbyController`, `QuantumPlugin`, `LobbyRunner` identifiées, RPCs à cartographier
- [ ] **Installer Il2CppDumper** pour obtenir la table complète des classes/méthodes (nécessite .NET ou compilation)
- [ ] **Analyser les RPC Photon spécifiques au jeu** (PunRPC) — rechercher dans les methodes de `CustomBattle.*`
- [ ] **Reconstruire le format des paquets Quantum** (ActorPhotonDataSerialize) — `DeterministicSessionConfig` de `PhotonDeterministic.dll`
- [ ] **Analyser les opcodes PlayFab personnalisés** : `matchBoxSkipTimeWithGems`, `deliverDynamicBundleS5`, `deliverSeasonalBundleS5`, `deliverEventRewardsS5`, `pingNodes`, `prepareNameChange`, `BypassKeychain`

## Priorité Moyenne

- [ ] Analyser le protocole de chat Photon (`ExitGames.Client.Photon.Chat`)
- [ ] Cartographier les événements analytics personnalisés (`Firebase.Analytics`, `Analytics.SendCustomEvent`)
- [ ] Décompiler les assets Unity (Spine, prefabs, textures) pour références visuelles
- [ ] Analyser le système de matchmaking déterministe Quantum (lockstep + frames)
- [ ] Étudier le système de combat (dégâts, hitbox, projectiles) — `DynamicProjectile`, `KinematicProjectile`
- [ ] Documenter le format des messages Quantum — `SimulationConfig`, `DeterministicSessionConfig`
- [ ] Analyser l'implémentation de `StartUp` (point d'entrée du jeu)

## Priorité Basse

- [ ] Analyser le système de bots (`ActorBotSystem`)
- [ ] Documenter le système de saison/défis (`ClubRoyale.*`, `XPBTSeasonEndTimes`)
- [ ] Analyser le système de coffres/gacha (`BattleChest`, `LuckyChest`)
- [ ] Étudier le Ring of Death (tempête) — non trouvé dans les chaînes
- [ ] Analyser le système de construction (`ActorBuildingSystem`)

## Bloquant (outils nécessaires)

- [ ] Installer Il2CppDumper (nécessite .NET ou compilation)
- [ ] Installer dotPeek / dnSpy pour décompiler les DLL PlayFab/Photon de référence
- [ ] Installer AssetStudio pour extraire les assets Unity et lire les ScriptableObjects
- [ ] Configurer un environnement de test avec Frida/packet capture pour analyse dynamique

## Questions en suspens

1. **PlayFab Title ID** — Non trouvé dans les chaînes, probablement dans l'objet sérialisé `PlayFabSharedSettings` (accessible via AssetStudio)
2. **Photon App ID** — 3 candidats identifiés : `bcf1bfc88d9114a88a8e0b503ef655cc` (Unity Build ID ?), `48f79e6d-4c67-4b5a-a4b5-c6d4216ea4cc`, `futureplay-1375e635-a30a-4958-9529-6a97436d4f86`
3. **Format exact des paquets Quantum** — Nécessite Il2CppDumper pour les structures
4. **Système de custom game** — Comment les parties personnalisées sont hébergées ? (`CustomBattle.RoomClosedError`, `CustomBattle.RoomFullError`, etc.)
5. **Protocole de synchronisation déterministe** — **Confirmé** : Quantum ECS lockstep sur Photon, avec `DeterministicSessionConfig` et `ReplayTools`
6. **Comment le Match Token est utilisé** — `MatchBoxTokenData`, `BoxTokenRefreshIntervalSeconds`, `matchBoxSkipTimeWithGems`, `DoubleTokensAvailable`
7. **Serveur Photon personnalisé ou émulateur** — Possible avec `Photon Server SDK` open-source ou `PhotonCloud` privé

## Progrès récents

- ✅ **BOOT_SEQUENCE.md** — Document complet de 7 phases couvrant le boot du jeu
- ✅ **SERVER_REQUIREMENTS.md** — Analyse complète des serveurs nécessaires (PlayFab, Photon, Firebase)
- ✅ **Classes clés identifiées** : `StartUp`, `ConfigLoader`, `PlayfabService`, `LobbyController`, `QuantumPlugin`, `QuantumRunner`
- ✅ **Structure de namespace confirmée** : `Futureplay.Quantum`, `CustomBattle.*`, `ClubRoyale.*`
- ✅ **PlayFab API calls utilisées** : `LoginWithCustomID`, `GetUserReadOnlyData`, `GetPhotonAuthenticationToken`, etc.
- ✅ **GUIDs candidats** : Photon AppId et identifiants trouvés dans `globalgamemanagers`
- ✅ **Méthodes de jeu** : 51 signatures extraites de `libil2cpp.so`
