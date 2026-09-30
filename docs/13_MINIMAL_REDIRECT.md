# 13 — Redirection minimale : APK 2.9.6 → notre backend → notre Photon

> Suite de `12_REBORN_ANALYSIS.md`. Tout ce qui suit a été vérifié par désassemblage de
> `libmain.so` Reborn (symboles non strippés) et par lecture de la table des littéraux de
> `global-metadata.dat`, sauf mention **[non vérifié]**.
>
> Outils : `client-patch/native/blr_redirect.c`, `client-patch/patch_metadata.py`.

## 1. Résumé

Reborn modifie **deux** choses, pas une :

| Élément | Rôle | Nécessaire pour nous |
|---|---|---|
| `libmain.so` (module `eu.c`) | Hook natif Photon → `ConnectToMaster(ip, 4530)` en TCP | Oui (réimplémenté, ~300 lignes) |
| `global-metadata.dat` (3 littéraux) | Redirige **le SDK PlayFab** vers leur backend | Oui (script de patch) |
| `libmain.so` (menu, clan, pseudo, carte, regles, lanceur, reseau, ui, amis, effets, classement, crash) | Fonctionnalités Reborn | Non |

Correction de `12_REBORN_ANALYSIS.md` §3/§34 : IL2CPP n'est **pas** intact —
`global-metadata.dat` est patché. `libil2cpp.so` n'a pas pu être comparé à un original
(l'app installée dans Waydroid est la Reborn, hashes identiques), mais rien dans `libmain.so`
ne suppose qu'il soit modifié.

## 2. Mécanisme natif exact (libmain.so Reborn)

```
JNI_OnLoad (0xa8140)
  dlopen("libmain_orig.so", RTLD_NOW) → dlsym("JNI_OnLoad") → appel   (boot Unity normal)
  reseau_demarrer()                         ← HTTP Reborn, inutile
  pthread_create(attendre_il2cpp)

attendre_il2cpp (0xa8218)
  boucle dlopen("libil2cpp.so", RTLD_NOW|RTLD_NOLOAD)  1200 × 100 ms
  il2cpp_resoudre()  → dlsym de ~30 exports il2cpp_*
  boucle il2cpp_get_corlib() != NULL, puis usleep(500 ms), il2cpp_thread_attach(domain)
  AudioManager.Update : remplacement de MethodInfo->methodPointer (hook UI, inutile)
  capture_installer() (vide), eu_installer()

eu_installer (0x9b1b0)
  PhotonNetwork, NetworkingPeer  (namespace "")      FuturePlay.GameSettings
  ConnectToMaster/4 (String, Int32, String, String)  SwitchToProtocol/1
  get_PhotonGameVersion/0
  thread surveiller() : connect() TCP non bloquant vers 88.96.61.105:4530 toutes les 30 s
                        → eu_joignable (repli Photon Cloud si injoignable — inutile pour nous)
  detourner(PhotonNetwork.ConnectToRegion/2)        → connect_region
  detourner(NetworkingPeer.ConnectToRegionMaster/1) → connect_region_master

connect_region(w0 = region, x1 = gameVersion)          [statique]
connect_region_master(x0 = this, w1 = region)         [instance]
  si region == 0 (CloudRegionCode.eu) && méthodes résolues && eu_joignable → vers_eu()
  sinon → trampoline d'origine

vers_eu (0x9b588)
  appId   = PhotonNetwork.PhotonServerSettings.AppID
  version = argument gameVersion, sinon GameSettings.get_PhotonGameVersion()
  SwitchToProtocol(1)                      ; ConnectionProtocol.Tcp (enum byte)
  return ConnectToMaster("88.96.61.105", 4530, appId, version)   ; bool unboxé à +0x10
```

**Point important** : Reborn ne redirige que la région `eu`. Les autres régions partent sur
Photon Cloud. Notre module redirige **toutes** les régions (`BLR_REDIRECT_ALL_REGIONS=1`).

### Hook inline (`detourner`, 0x99e08)

- Refuse si l'une des 4 premières instructions est PC-relative (ADR/ADRP, B/BL, CBZ/TBZ, B.cond, LDR literal).
- Trampoline `mmap` RWX 32 octets : 4 instructions d'origine + `LDR X16,#8 ; BR X16 ; .quad cible+16`.
- Cible : `mprotect` RWX puis `LDR X16,#8 ; BR X16 ; .quad hook` (16 octets).
- Reborn laisse la page RWX ; notre version la remet en R-X.

Les méthodes C# étant appelées par `BL` direct depuis le code IL2CPP, un simple échange de
`MethodInfo->methodPointer` ne suffit pas pour ces deux méthodes : le hook inline est nécessaire.

## 3. Redirection PlayFab (global-metadata.dat)

Table des littéraux (métadonnées v24, 12 099 littéraux). Originaux retrouvés dans les
données orphelines du blob :

| Littéral | Original 2.9.6 | Reborn |
|---|---|---|
| #7556 | `playfabapi.com` | `https://b.88-96-61-105.sslip.io` |
| #7819 | `.playfabapi.com/Client/LinkCustomID` | `@b.88-96-61-105.sslip.io/Client/LinkCustomID` |
| #7823 | `.playfabapi.com/Client/LoginWithFacebook` | `@b.88-96-61-105.sslip.io/Client/LoginWithFacebook` |

- #7556 est l'URL de base du SDK PlayFab : commençant par `http`, elle est utilisée telle quelle
  au lieu de `https://<TitleId>.playfabapi.com`.
- #7819/#7823 sont concaténées à `"https://" + TitleId` dans le code du jeu ; le `@` transforme
  le TitleId en userinfo : `https://299E@b.…sslip.io/Client/LinkCustomID`.
- Reborn a fait de la place en **écrasant** trois autres littéraux (#1998, #2011 : noms
  d'algorithmes crypto Mono ; #6694 : chaîne du SDK Facebook). `patch_metadata.py` ajoute plutôt
  les chaînes en fin de fichier et ne repointe que les trois entrées : IL2CPP v24 lit
  `stringLiteralData + dataIndex` sans contrôle de borne sur un fichier mappé en entier.

### Contrainte TLS

Manifeste : `targetSdkVersion 30`, pas de `usesCleartextTraffic`, pas de
`networkSecurityConfig` → le HTTP en clair est bloqué pour la pile Java. Le backend PlayFab doit
donc être servi en **HTTPS avec un certificat valide**. C'est la raison du `sslip.io` de Reborn :
`b.<ip-avec-tirets>.sslip.io` résout vers l'IP et permet à Caddy d'obtenir un certificat
Let's Encrypt. Même approche pour nous (Caddy → Flask :5000). Photon (socket TCP brute) n'est
pas concerné.

## 4. PlayFab minimal pour obtenir le token Photon

`GetPhotonAuthenticationToken` (SDK PlayFab Unity 2.66.190509) :

```
POST /Client/GetPhotonAuthenticationToken
X-Authorization: <SessionTicket>
{"PhotonApplicationId": "<AppID Photon>"}

→ {"code":200,"status":"OK","data":{"PhotonCustomAuthenticationToken":"<token>"}}
```

Corrigé dans `battlelands-server/playfab/auth.py` : il renvoyait
`PhotonAuthenticationToken.Token`, que le SDK ne lit pas (champ `null` côté client).

Prérequis : un login PlayFab qui émet un `SessionTicket`. Le reste de la séquence avant Photon
(CloudScripts `startSeason14`/`initializeDataS5`/`getSupportData`, title data, inventaire…) ne
peut pas être établi statiquement sans dump IL2CPP ; il faut le lire dans les logs du backend
une fois PlayFab redirigé (chaque route inconnue apparaît en 404 dans le log Flask).

## 5. Paramètres Photon indispensables

| Paramètre | Valeur | Source |
|---|---|---|
| Adresse master | IP compilée dans `libmain.so` | `BLR_PHOTON_HOST` |
| Port | 4530 | port TCP master par défaut de Photon Server |
| Protocole | TCP (`ConnectionProtocol.Tcp` = 1) | `SwitchToProtocol` |
| AppID | `PhotonServerSettings.AppID`, inchangé | lu à l'exécution, loggé |
| Version | `GameSettings.PhotonGameVersion` | lu à l'exécution, loggé |
| Auth | `PhotonNetwork.AuthValues` posé par le jeu **[non vérifié]** | voir ci-dessous |

- `ConnectToMaster` n'utilise pas le NameServer : l'`OpAuthenticate` (AppId, AppVersion,
  AuthValues) est envoyé **directement au master**. Pour un premier test, le serveur Photon doit
  accepter toute authentification ; la validation du token PlayFab viendra ensuite.
- PUN classique suffixe la version envoyée par `_<versionPUN>` **[non vérifié]** : ne pas filtrer
  sur une version exacte côté serveur.
- Pour rejoindre une room, le master renvoie l'adresse du game server : elle doit être l'IP
  publique (en TCP, 4531 par défaut sur Photon Server).
- `ConnectToMaster` exige l'état `Disconnected`. Si le jeu passe par
  `ConnectToBestCloudServer` puis `ConnectToRegionMaster` alors qu'il est déjà connecté au
  NameServer, l'appel redirigé renverra `false` (visible dans le log). Reborn a le même
  comportement, ce qui suggère que le jeu passe par `ConnectToRegion`.

## 6. Assemblage de l'APK modifiée

Depuis l'APK **originale** 2.9.6 (pas la Reborn) :

```bash
# 1. natif
ANDROID_NDK_HOME=... client-patch/native/build.sh <ip_photon> 4530   # BLR_DRY_RUN=1 pour le 1er test
unzip orig.apk -d apk/
mv apk/lib/arm64-v8a/libmain.so apk/lib/arm64-v8a/libmain_orig.so
cp client-patch/native/out/libmain.so apk/lib/arm64-v8a/

# 2. PlayFab
client-patch/patch_metadata.py apk/assets/bin/Data/Managed/Metadata/global-metadata.dat \
    b.<ip-avec-tirets>.sslip.io -o /tmp/gm.dat
mv /tmp/gm.dat apk/assets/bin/Data/Managed/Metadata/global-metadata.dat

# 3. reconstruire : resources.arsc NON compressé (obligatoire en targetSdk 30), puis signer
rm -rf apk/META-INF/*.SF apk/META-INF/*.RSA apk/META-INF/*.MF
(cd apk && zip -qr -0 ../out.apk resources.arsc && zip -qr ../out.apk . -x resources.arsc)
zipalign -p -f 4 out.apk aligned.apk
apksigner sign --ks debug.keystore --out battlelands-private.apk aligned.apk
```

Désinstaller l'app existante avant installation (signature différente). Logs :
`adb logcat -s BLRRedirect`.

## 7. Jalons de test

1. `BLR_DRY_RUN=1` : le log doit afficher `hook : … detourne` ×2, puis au lancement d'une partie
   `region N -> … AppID=… version=… [DRY RUN]`. Cela confirme AppID, version et le chemin de
   connexion réellement emprunté, sans rien casser.
2. PlayFab redirigé : relever dans le log Flask la séquence exacte des routes jusqu'à
   `GetPhotonAuthenticationToken`.
3. `BLR_DRY_RUN=0` : `ConnectToMaster -> true`, connexion TCP visible sur le serveur Photon, puis
   `OnConnectedToMaster` → lobby → room → Quantum.

## 8. Points ouverts

- APK 2.9.6 originale : non présente sur cette machine (Waydroid contient la Reborn).
- Dump IL2CPP complet (Il2CppDumper) non réalisé : il confirmerait les valeurs d'enum, le code
  qui pose `AuthValues`, et quel chemin de connexion le jeu utilise. Le jalon 1 (dry-run) donne
  la même information à l'exécution.
- Choix du serveur Photon (Photon Server SDK auto-hébergé ou réimplémentation) : à traiter
  séparément ; les contraintes minimales sont en §5.
