# 14 — Les 13 patchs de Reborn dans libil2cpp.so

> Méthode : dump Il2CppDumper (commit `4741d46`) de `libil2cpp.so` + `global-metadata.dat`
> de l'APK **originale** 2.9.6 (métadonnées v24.1, CodeRegistration `0x3244e40`), puis
> `cmp` octet à octet avec le `libil2cpp.so` de Reborn (même taille, 82 octets différents).
> RVA = offset fichier (1er segment chargé à 0). Code original désassemblé avec résolution
> des appels / métadonnées (relocations `R_AARCH64_RELATIVE` + `script.json`).

## 1. Tableau

| # | RVA méthode (octets patchés) | Classe | Méthode | Original | Reborn | Rôle |
|---|---|---|---|---|---|---|
| 1 | `0xF2D1D8` (+4) | `FuturePlay.ChatController.<>c` | `<PostInit>b__13_6(PhotonNetworkState photon, bool chat) : PhotonNetworkState` | `chat ? photon : Disconnected(1)` | `return photon` | **établi** : l'état réseau affiché ne dépend plus de la connexion Photon Chat. *Inféré* : Chat non hébergé. |
| 2 | `0xF4B1E8` | `FuturePlay.BattlePassRunner` | `GetSeasonTimeleftNow() : long` | `(début saison + TimeSpan.FromMilliseconds(GameSettings…)) − ServerTimeService.NowTicks` | `return 0xE7BE2C00` (3 888 000 000) | **établi** : temps restant de saison constant. *Inféré* : saison jamais terminée (45 j si l'unité est la ms, non vérifié). |
| 3 | `0xF9A1BC` (+4) | `FuturePlay.UIMessaging.<>c` | `<Start>b__11_1(UIId s) : bool` | `s == UIId.NewsPopup (119)` | `return true` | **établi** : le filtre d'ouverture d'écran laisse tout passer (messages/news). Cosmétique. |
| 4 | `0xFA8F00` | `FuturePlay.DailyFreeItemRunner` | `ShowAd(AdPlacement, ClaimableReward)` | affiche une pub récompensée | appel direct `OnAdFinished(placement, reward)` | **établi** : récompense quotidienne sans pub. |
| 5 | `0xFAA118` | `FuturePlay.DebugException` | `HandleException(string condition, string stackTrace, LogType type)` | si `type == Exception (4)` → `SceneLoadHelper.LoadInitSceneNow()` | `ret` | **établi** : une exception non gérée ne **relance plus le jeu**. |
| 6 | `0xFEFAE4` | `FuturePlay.UIDailyFreeItem.<>c` | `<Awake>b__15_0(bool adReady, bool claimed) : bool` | `adReady && !claimed` | `!claimed` | **établi** : l'objet gratuit n'exige plus une pub prête. |
| 7 | `0x103E3B0` | `FuturePlay.GameLoader` | `HaventAcceptedYet() : bool` | `PlayerData.Instance.AcceptedVersion < GameSettings.Instance.MinimumAcceptedVersion` | `return false` | **établi** : jamais de popup CGU/Confidentialité (`ShowTOSAndPPPopup` + `WaitUntil` à 100 %). |
| 8 | `0x103E9E0` | `FuturePlay.GameLoader.<>c` | `<LoadingRoutine>b__9_1() : bool` | `FacebookAPIService.FBInited` | `return true` | **établi** : `LoadingRoutine` n'attend plus l'init du SDK Facebook avant `PlayFabRunner.LoginSequence` (après 35 %). |
| 9 | `0x1079670` | `FuturePlay.UILobby` | `static CheckBattleTagName(string) : bool` | validation du pseudo | `return true` | **établi** : tout pseudo accepté. |
| 10 | `0x115BB28` | `FuturePlay.LobbyUIProperties.<>c` | `<PostInit>b__124_53(Tuple<FacebookEvent,object>)` | `SceneLoadHelper.LoadInitSceneNow()` | `ret` | **établi** : un événement Facebook ne relance plus le jeu (événement précis non identifié). |
| 11 | `0x12630B8` | `PhotonPingManager` | `get_Done : bool` | `PingsRunning == 0` | `return true` | **établi** : le ping des régions est toujours « terminé ». |
| 12 | `0x126E538` | `PhotonPingManager.<PingSocket>d__10` | `MoveNext() : bool` | coroutine de ping d'une région | `return false` | **établi** : aucun ping de région n'est effectué. |
| 13 | `0x131A53C` | `AdService` | `RegisterProvider(AdProvider)` | enregistre Unity Ads / Facebook / AdMob | `ret` | **établi** : aucun fournisseur de pub enregistré. |

Classement par rôle :

- **Démarrage / robustesse** : #5, #7, #8, #10
- **Photon (ping de région, meilleur serveur)** : #11, #12 (et #1 pour l'état affiché)
- **Publicités** : #4, #6, #13
- **Contenu / confort** : #2 (saison), #3 (news), #9 (pseudo)

## 2. Le blocage à « 1 » dans Waydroid ne vient d'aucun de ces 13 patchs

`GameLoader.Start` (`0x103CAF0`) :

```
SetLoadingText("1")
PlayFabRunner.ReadPlayFabId() → SetPlayFabIDText
if (GooglePlayServicesChecker.UpToDate())      // 0x103CFF4
    StartCoroutine(LoadingRoutine())           // "5" … "100"
else
    Observable.EveryApplicationPause().Where(…).Take(…).Subscribe(…)   // réessai au retour
```

`GooglePlayServicesChecker.UpToDate()` appelle en JNI
`gpsplugin.futureplay.com.gpscheck.GPSChecker.checkPlayServices(currentActivity)` (Java).
Sans Google Play Services, elle renvoie `false` : `LoadingRoutine` ne démarre jamais,
l'écran reste à « 1 ». Aucun littéral `"1"` n'existe dans `LoadingRoutine` : « 1 » n'est
posé que par `Start`, avant ce test.

Reborn **ne contourne pas** ce contrôle :

- `UpToDate()` est identique octet pour octet dans le `libil2cpp.so` de Reborn ;
- `classes.dex` et `classes2.dex` sont identiques (mêmes CRC) ;
- rien dans `libmain.so` Reborn ne le vise (cf. doc 12/13).

Reborn a donc besoin de Google Play Services comme l'original ; dans cette image Waydroid
sans GMS, Reborn serait bloqué au même endroit.

Parmi les 13, seul **#8** agit sur le même chemin de démarrage (attente Facebook, bien plus
loin, après 35 %). **#5** est aussi pertinent pour la suite : sans lui, toute exception non
gérée (p. ex. une réponse PlayFab incomplète) relance la scène d'init — candidat sérieux
pour la boucle `CheckAndUpdateSeason` décrite en doc 12 §28.

## 3. Autres différences Reborn / originale (hors périmètre, non analysées)

`unzip -v` des deux APK : `classes*.dex` identiques ; différences dans
`globalgamemanagers`, `level1.split*`, 3 fichiers `assets/bin/Data/<hash>`, et ajouts
`level6.split*` (49), `sharedassets6/7.*`, `globalgamemanagerz.assets.split*` — cohérent
avec les cartes/modes custom de Reborn.

## 4. Test expérimental : bypass GooglePlayServicesChecker (2026-09-30)

Patch unique (pas un patch Reborn), `client-patch/patch_il2cpp_gps.py` :

| Fichier | RVA | Méthode | Avant | Après |
|---|---|---|---|---|
| `lib/arm64-v8a/libil2cpp.so` | `0x103CFF4` | `static bool FuturePlay.GooglePlayServicesChecker.UpToDate()` | `f50f1df8 f44f01a9` (`str x21,[sp,#-0x30]!` ; `stp x20,x19,[sp,#0x10]`) | `20008052 c0035fd6` (`mov w0,#1` ; `ret`) |

Appelants directs : `GameLoader.Start` (`0x103CB68`) et `GameLoader.<>c.<Start>b__7_0`
(`0x103E950`, réessai au retour de pause). APK : `build/gps-bypass/battlelands-gps-bypass-experimental.apk`
(= APK du test dry-run + ce seul `libil2cpp.so`).

Résultat Waydroid (sans GMS) : `LoadingRoutine` démarre ; Facebook init OK, Firebase RemoteConfig
échoue sans bloquer, « Quantum Asset Database Loaded », puis `PlayFabRunner.LoginSequence` →
`POST https://b.127-0-0-1.sslip.io/Client/LoginWithAndroidDeviceID` → `UnknownHostException`
→ `PlayfabService - LoginAndLoadData Error` → popup « Connection Error » (écran à 40) → nouvel
essai. Hooks Photon installés mais non invoqués (attendu : Photon vient après le login).
Premier appel PlayFab réel : **`LoginWithAndroidDeviceID`** (pas `LoginWithCustomID`).
