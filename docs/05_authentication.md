# Système d'authentification

## Flow d'authentification

```
1. Démarrage du jeu
   │
2. Génération/récupération d'un Device ID (Android_ID)
   │   Fichier: /customid.txt
   │
3. Login PlayFab avec LoginWithCustomID ou LoginWithAndroidDeviceID
   │
4. Si premier lancement -> création automatique de compte
   │
5. Récupération du SessionTicket et EntityToken
   │
6. GetPhotonAuthenticationToken -> Token Photon
   │
7. Connexion Photon avec le token
   │
8. Récupération des données joueur via GetUserData, GetUserReadOnlyData
   │
9. Récupération de l'inventaire via GetUserInventory
   │
10. Récupération du catalogue via GetCatalogItems / GetStoreItems
```

## Méthodes de login supportées

### Primaires
1. **LoginWithAndroidDeviceID** - Login automatique via l'Android ID
2. **LoginWithCustomID** - Fallback avec Custom ID stocké dans `/customid.txt`

### Secondaires (liens de compte)
3. **LoginWithFacebook** - Connexion Facebook
4. **LoginWithGoogleAccount** - Connexion Google
5. **LoginWithApple** - Connexion Apple
6. **LoginWithGameCenter** - Connexion Game Center (iOS)
7. **LoginWithSteam** - Connexion Steam

## Données stockées localement

| Fichier | Contenu |
|---------|---------|
| `/customid.txt` | Custom ID pour PlayFab |
| `/pfid.txt` | PlayFab ID |
| `PlayerPrefs` | Session, tokens, préférences |

## Headers d'authentification

```
X-Authorization: <SessionTicket>
X-EntityToken: <EntityToken>
X-PlayFabSDK: UnitySDK-2.66.190509
X-AuthenticationTimestamp: <timestamp>
```

## Clés PlayFab

Les noms de clés de données utilisées :
- `TitleId` - à configurer dans PlayFabSharedSettings
- `AccessToken` - Token d'accès
- `SessionTicket` - Ticket de session
- `EntityToken` - Token d'entité

## Firebase Auth

Firebase Auth est également initialisé mais principalement utilisé pour Remote Config et Analytics, pas pour l'authentification principale du jeu.
