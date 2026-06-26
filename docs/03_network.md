# Analyse réseau

## Architecture réseau

```
┌─────────────┐     HTTPS/JSON     ┌─────────────────┐
│  Client     │ ────────────────>  │  PlayFab API    │
│  (Unity)    │ <──────────────── │  (REST)          │
│             │     JSON           │                  │
│             │                    │  *.playfabapi    │
│             │                    │  .com            │
├─────────────┤                    └─────────────────┘
│  Photon     │     TCP/WebSocket  ┌─────────────────┐
│  Peer       │ ────────────────>  │  Photon Cloud   │
│  (UDP/TCP)  │ <──────────────── │  (Exit Games)   │
│             │    Binaire Photon  │                  │
│             │                    │  *.exitgames.com │
└─────────────┘                    └─────────────────┘
```

## Protocoles

### HTTP/HTTPS (PlayFab REST API)
- **Format** : JSON (Newtonsoft.Json)
- **Headers** : `X-Authorization`, `X-EntityToken`, `X-PlayFabSDK`, `X-AuthenticationTimestamp`
- **Encodage** : UTF-8
- **Cache** : Certaines réponses sont mises en cache localement (catalogue IAP)

### Photon (Real-time)
- **Transport** : WebSocket (ws://, wss://) ou TCP
- **Protocole** : Protocole binaire propriétaire Photon
- **Sérialisation** : Photon custom (ExitGames.Client.Photon)
- **Encryption** : Activée automatiquement pendant la connexion
- **Peer** : `LoadBalancingPeer` avec `QuantumNetworkCommunicator`

## Certificats SSL/TLS

Le jeu utilise les certificats SSL standards. Aucun certificat personnalisé n'a été trouvé.

## Adresses et Domaines

| Domaine | Usage | Protocole |
|---------|-------|-----------|
| `*.playfabapi.com` | PlayFab REST API | HTTPS |
| `ns.exitgames.com` | Photon Name Server | TCP |
| `*.exitgames.com` | Photon Cloud | WebSocket/TCP |
| `https://catalog.iap.cloud.unity3d.com` | Catalogue Unity IAP | HTTPS |
| `https://connect.facebook.net` | Facebook SDK | HTTPS |
| `https://graph.facebook.com` | Facebook Graph API | HTTPS |
| `https://play.google.com` | Google Play Store | HTTPS |

## Deep Links

| Scheme | Usage |
|--------|-------|
| `blr://` | Deep link principal |
| `blr://inviteFriend/` | Invitation d'ami |
| `blr://customBattle/` | Partie personnalisée |
| `battlelands://` | Facebook App Link |

## Rôles Photon

Le jeu utilise le système de rôles Photon standard :
- **MasterClient** : Autorité sur la room (gère les pickups, le spawn, etc.)
- **Clients** : Joueurs normaux
- **ExpectedUsers** : Gestion des joueurs attendus

## Classes réseau identifiées

| Classe | Rôle |
|--------|------|
| `QuantumNetworkCommunicator` | Wrapper autour de Photon LoadBalancingPeer |
| `LoadBalancingPeer` | Peer Photon pour les opérations réseau |
| `ActorPhotonData` | Données de l'acteur synchronisées via Photon |
| `ActorPhotonDataSerialize` | Sérialisation des données acteur |
| `PhotonView` | Vue Photon pour la synchronisation |
| `PhotonTransformView` | Synchronisation des transformations |
| `PhotonAnimatorView` | Synchronisation des animations |
| `PhotonRigidbody2DView` | Synchronisation des rigidbodies 2D |
| `PunPickup` | Pickup synchronisé via Photon |
| `PunRespawn` | Respawn synchronisé |
