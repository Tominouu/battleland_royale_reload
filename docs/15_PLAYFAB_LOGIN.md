# 15 — Premier login PlayFab (LoginWithAndroidDeviceID) depuis Waydroid

> APK testée : `build/gps-bypass/battlelands-gps-bypass-experimental.apk` (inchangée : métadonnées
> patchées vers `b.127-0-0-1.sslip.io` + bypass `GooglePlayServicesChecker.UpToDate`, cf. doc 14).

## 1. Comment le client obtient l'URL PlayFab

`PlayFab.PlayFabSettings.GetFullUrl(apiCall, getParams, apiSettings)` (RVA `0xFC36B4`) :

```
base = apiSettings.ProductionEnvironmentUrl
    ?? PlayFabSharedSettings.ProductionEnvironmentUrl
    ?? "playfabapi.com"                      // littéral #7556 de global-metadata.dat
if base.StartsWith("http"):  url = base + apiCall
else:                        url = "https://" + TitleId + "." + [VerticalName + "."] + base + apiCall
```

L'asset `PlayFabSharedSettings` ne définit pas d'URL (la requête observée part vers notre hôte),
donc c'est le littéral #7556, remplacé par `patch_metadata.py` par `https://b.127-0-0-1.sslip.io`
(chaîne ajoutée en fin de `global-metadata.dat`). `TitleId` envoyé : **`299E`**.

Transport : `PlayFab.Internal.PlayFabUnityHttp` → `UnityWebRequest` → pile Java Android
(`HttpURLConnection`). Aucune classe du jeu ne dérive de `CertificateHandler` : validation TLS
standard sur le magasin de CA **système** (targetSdk 30 : CA utilisateur ignorées).

## 2. Joignabilité depuis Waydroid (solution de test, sans modifier l'APK)

`b.127-0-0-1.sslip.io` → 127.0.0.1 publiquement (boucle locale d'Android) et aucun certificat
public n'est obtenable pour ce nom. Solution retenue, limitée à l'environnement Waydroid :

| Élément | Valeur |
|---|---|
| Backend | gunicorn HTTPS `192.168.240.1:443` (pont `waydroid0` uniquement), worker en utilisateur `tom` |
| Certificat | `build/tls/server.pem` (SAN `b.127-0-0-1.sslip.io`, 192.168.240.1), signé par `build/tls/ca.pem` |
| Overlay DNS | `/var/lib/waydroid/overlay/system/etc/hosts` : `192.168.240.1 b.127-0-0-1.sslip.io` |
| Overlay CA | `/var/lib/waydroid/overlay/system/etc/security/cacerts/4bd3b6ba.0` (`subject_hash_old`) |

Retour arrière : supprimer ces deux fichiers d'overlay, puis `waydroid session stop` / `start`.
Les overlays ne sont pris en compte qu'au montage du rootfs : `waydroid container restart` ne
suffit pas, il faut arrêter puis relancer la session.

Vérifié depuis Android : résolution `192.168.240.1`, TCP 443 OK, `curl --capath
/system/etc/security/cacerts` → `ssl_verify_result=0`, POST login → 200.

Note : l'échec DNS observé plus tôt dans Waydroid n'était **pas** un filtrage des `sslip.io` :
après un redémarrage du framework Android, le conteneur n'avait plus de réseau par défaut
(`Active default network: none`) ; un redémarrage de session l'a rétabli.

## 3. `POST /Client/LoginWithAndroidDeviceID`

Requête réelle du client (SDK `UnitySDK-2.66.190509`) :

```json
{"AndroidDevice": null, "AndroidDeviceId": "2689025a0950023e2b3d573bc35bc723", "CreateAccount": true,
 "EncryptedRequest": null, "OS": null, "PlayerSecret": null, "TitleId": "299E", "AuthenticationContext": null,
 "InfoRequestParameters": {"GetPlayerStatistics": true, "GetTitleData": true, "GetUserAccountInfo": true,
   "GetUserInventory": true, "GetUserReadOnlyData": true, "GetUserVirtualCurrency": true,
   "GetCharacterInventories": false, "GetCharacterList": false, "GetPlayerProfile": false, "GetUserData": false,
   "PlayerStatisticNames": null, "ProfileConstraints": null, "TitleDataKeys": null, "UserDataKeys": null,
   "UserReadOnlyDataKeys": null}}
```

Réponse (`battlelands-server/playfab/auth.py`, champs = `PlayFab.ClientModels.LoginResult` du dump) :

```json
{"code": 200, "status": "OK", "data": {
  "PlayFabId": "<16 hex>", "SessionTicket": "<PlayFabId>-<16 hex>-<32 hex>",
  "NewlyCreated": true, "LastLoginTime": "<UTC ISO>",
  "EntityToken": {"EntityToken": "<64 hex>", "TokenExpiration": "2099-01-01T00:00:00Z",
                  "Entity": {"Id": "<PlayFabId>", "Type": "title_player_account"}},
  "SettingsForUser": {"NeedsAttribution": false, "GatherDeviceInfo": true, "GatherFocusInfo": true},
  "InfoResultPayload": {"AccountInfo": {...}, "PlayerStatistics": [], "TitleData": {}, "UserInventory": [],
                        "UserReadOnlyData": {}, "UserVirtualCurrency": {}, "UserDataVersion": 0,
                        "UserReadOnlyDataVersion": 0}}}
```

PlayFabId en 16 hex : le client le convertit (`TeamHelper.PlayFabIdToUInt64`). Le même
`AndroidDeviceId` retrouve le même compte (mémoire du processus uniquement pour l'instant).
Chaque appel est journalisé dans `battlelands-server/logs/requests.jsonl`.

## 4. Résultat : séquence réelle après le login

```
15:49:41  LoginWithAndroidDeviceID               200  → LoginResult accepté, appels suivants authentifiés
15:49:41  ReportDeviceInfo          (session)    404  → non bloquant : "OnGatherFail" (log Info)
15:49:41  ExecuteCloudScript        (session)    404  ×4, FunctionName "startSeason14", FunctionParameter null
          → "PlayfabService - LoginAndLoadData Error : /Client/ExecuteCloudScript: Unknown endpoint"
          → popup « Connection Error » à 40, plus aucun appel
```

Nouveau blocage : **`ExecuteCloudScript("startSeason14")`**, dans `PlayFabRunner.LoginSequence`
(côté PlayFab/backend). Même fonction que la boucle `CheckAndUpdateSeason` du doc 12 §28.
