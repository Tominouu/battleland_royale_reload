# Endpoints API

## PlayFab Client API

Tous les endpoints sont sous `.playfabapi.com`. Le jeu utilise l'API Client de PlayFab.

### Authentification

| Endpoint | Méthode |
|----------|---------|
| `/Client/LoginWithAndroidDeviceID` | Login avec Android ID |
| `/Client/LoginWithCustomID` | Login avec Custom ID |
| `/Client/LoginWithFacebook` | Login Facebook |
| `/Client/LoginWithGoogleAccount` | Login Google |
| `/Client/LoginWithApple` | Login Apple (présent dans les références) |
| `/Client/LoginWithSteam` | Login Steam |
| `/Client/LoginWithGameCenter` | Login Game Center |
| `/Client/LoginWithIOSDeviceID` | Login iOS Device |
| `/Client/LoginWithPlayFab` | Login avec email/mot de passe |
| `/Client/LoginWithTwitch` | Login Twitch |
| `/Client/LoginWithXbox` | Login Xbox |
| `/Client/LoginWithPSN` | Login PlayStation |
| `/Client/LoginWithKongregate` | Login Kongregate |
| `/Client/LoginWithFacebookInstantGamesId` | Login Facebook Instant |
| `/Client/LoginWithNintendoSwitchDeviceId` | Login Nintendo Switch |
| `/Client/LinkCustomID` | Lier Custom ID au compte |
| `/Client/RegisterPlayFabUser` | Créer un compte |
| `/Client/GetPhotonAuthenticationToken` | Token Photon |

### Joueur / Profil

| Endpoint | Usage |
|----------|-------|
| `/Client/GetAccountInfo` | Info de base du compte |
| `/Client/GetPlayerCombinedInfo` | Info combinée du joueur |
| `/Client/GetPlayerProfile` | Profil détaillé |
| `/Client/GetPlayerStatistics` | Statistiques |
| `/Client/GetPlayerStatisticVersions` | Versions des stats |
| `/Client/UpdatePlayerStatistics` | Mettre à jour les stats |
| `/Client/GetPlayerTags` | Tags du joueur |
| `/Client/GetPlayerSegments` | Segments du joueur |
| `/Client/GetPlayerTrades` | Échanges |

### Données utilisateur

| Endpoint | Usage |
|----------|-------|
| `/Client/GetUserData` | Données utilisateur |
| `/Client/GetUserReadOnlyData` | Données read-only |
| `/Client/GetUserInventory` | Inventaire |
| `/Client/UpdateUserData` | Mettre à jour données |
| `/Client/AddUserVirtualCurrency` | Ajouter monnaie virtuelle |
| `/Client/SubtractUserVirtualCurrency` | Enlever monnaie virtuelle |

### Catalogue / Boutique

| Endpoint | Usage |
|----------|-------|
| `/Client/GetCatalogItems` | Catalogue d'items |
| `/Client/GetStoreItems` | Boutique |
| `/Client/PurchaseItem` | Acheter un item |
| `/Client/ConfirmPurchase` | Confirmer un achat |
| `/Client/StartPurchase` | Commencer un achat |
| `/Client/GetPaymentToken` | Token de paiement |
| `/Client/PayForPurchase` | Payer l'achat |
| `/Client/ConsumeItem` | Consommer un item |
| `/Client/UnlockContainerInstance` | Ouvrir un coffre |
| `/Client/UnlockContainerItem` | Débloquer item de coffre |

### Matchmaking

| Endpoint | Usage |
|----------|-------|
| `/Client/Matchmake` | Matchmaking standard |
| `/Client/StartGame` | Démarrer une partie |
| `/Client/GetCurrentGames` | Lister les parties en cours |
| `/Client/GetGameServerRegions` | Régions serveur disponibles |

### PlayFab Multiplayer Server (Nouveau)

| Endpoint | Usage |
|----------|-------|
| `/Match/CreateMatchmakingTicket` | Créer ticket de matchmaking |
| `/Match/CancelMatchmakingTicket` | Annuler ticket |
| `/Match/GetMatchmakingTicket` | Statut du ticket |
| `/Match/GetMatch` | Info sur le match |
| `/Match/JoinMatchmakingTicket` | Rejoindre un ticket |
| `/Match/ListMatchmakingTicketsForPlayer` | Tickets du joueur |
| `/MultiplayerServer/RequestMultiplayerServer` | Demander serveur |
| `/MultiplayerServer/GetMultiplayerServerDetails` | Détails serveur |
| `/MultiplayerServer/ShutdownMultiplayerServer` | Éteindre serveur |
| `/MultiplayerServer/GetQosServers` | Serveurs QoS |

### Groupes / Amis

| Endpoint | Usage |
|----------|-------|
| `/Client/GetFriendsList` | Liste d'amis |
| `/Client/AddFriend` | Ajouter ami |
| `/Client/RemoveFriend` | Supprimer ami |
| `/Client/SetFriendTags` | Tags d'amis |
| `/Group/AddMembers` | Ajouter membre au groupe |
| `/Group/CreateGroup` | Créer groupe |
| `/Group/InviteToGroup` | Inviter au groupe |

### Événements

| Endpoint | Usage |
|----------|-------|
| `/Event/WriteEvents` | Envoyer événements analytics |
| `/Client/WritePlayerEvent` | Événement joueur |
| `/Client/WriteTitleEvent` | Événement du titre |

### Contenu

| Endpoint | Usage |
|----------|-------|
| `/Client/GetContentDownloadUrl` | URL de téléchargement contenu |
| `/Client/GetTitleData` | Données du titre |
| `/Client/GetTitleNews` | Actualités du titre |
| `/Client/GetTime` | Heure serveur |

## Autres endpoints

### Unity IAP Cloud Catalog
```
https://catalog.iap.cloud.unity3d.com/{0}/{1}
```

### Facebook Graph API
```
https://graph.facebook.com/me/permissions
https://graph.facebook.com/me?fields=id
```

## PlayFab Policy

Le jeu utilise aussi :
- `/Profile/GetProfile`
- `/Profile/GetGlobalPolicy`
- `/Profile/SetProfilePolicy`
