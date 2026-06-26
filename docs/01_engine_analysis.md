# Analyse du moteur

## Moteur : Unity 2018.4.31f1

Identifié via la chaîne suivante dans `libil2cpp.so` :

```
/Applications/Unity/Hub/Editor/2018.4.31f1/Unity.app/Contents/il2cpp/libil2cpp/
```

## Backend IL2CPP

Le jeu utilise **IL2CPP** (Intermediate Language To C++) comme backend de script Unity. Cela signifie que le code C# original (Assembly-CSharp) est compilé en code C++ natif, puis en une bibliothèque partagée.

### Fichiers IL2CPP

| Fichier | Taille | Description |
|---------|--------|-------------|
| `lib/arm64-v8a/libil2cpp.so` | ~55 MB | Code du jeu compilé (C# -> C++ natif) |
| `assets/bin/Data/Managed/Metadata/global-metadata.dat` | ~10 MB | Métadonnées IL2CPP (classes, méthodes, chaînes) |
| `lib/arm64-v8a/libunity.so` | ~15.7 MB | Moteur Unity natif |
| `lib/arm64-v8a/libmain.so` | ~6 KB | Point d'entrée Unity |

### Assemblées détectées

- `Assembly-CSharp` - Code principal du jeu
- `Assembly-CSharp-firstpass` - Code des plugins en firstpass
- `Assembly-CSharp-testable` - Tests (présents dans le build final !)
- `Assembly-CSharp-Editor-testable` - Tests Editor

## Plugins natifs

| Bibliothèque | Description |
|-------------|-------------|
| `libFirebaseCppAnalytics.so` | Firebase Analytics |
| `libFirebaseCppApp-6_12_0.so` | Firebase Core v6.12.0 |
| `libFirebaseCppRemoteConfig.so` | Firebase Remote Config |

## Plugins Unity (SDKs)

- **Photon PUN** - Réseau multijoueur (Exit Games)
- **PlayFab SDK v2.66.190509** - Backend as a Service
- **Facebook SDK v8.0+** - Social, login, ads
- **Firebase** (Analytics, Remote Config, Auth, Instance ID)
- **Google AdMob** - Publicité
- **Unity Ads** - Publicité
- **Unity IAP** - Achats intégrés
- **Spine** - Animation 2D squelettique
- **Cinemachine** - Caméras virtuelles
- **Newtonsoft.Json** - Sérialisation JSON
- **AppsFlyer** - Attribution
- **Unity Notifications** (net.agasper) - Notifications push
