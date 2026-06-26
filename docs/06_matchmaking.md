# Système de matchmaking

## Modes de jeu

| Mode | Description |
|------|-------------|
| **Solo** | 1 joueur, tous contre tous |
| **Duo** | Équipes de 2 |
| **Squad** | Équipes de 4 (ou 3?) |
| **Custom Battle** | Partie personnalisée (bots, mode, etc.) |

## Flow de matchmaking

### Matchmaking standard (PlayFab)

```
Client                     PlayFab                   Photon
  │                          │                        │
  ├─ LoginWithCustomID ─────>│                        │
  │<── SessionTicket ────────┤                        │
  │                          │                        │
  ├─ GetPhotonAuthentication ┤                        │
  │  Token                   │                        │
  │<── PhotonToken ──────────┤                        │
  │                          │                        │
  ├─ Matchmake ─────────────>│                        │
  │                          │                        │
  │ (recherche d'adversaires)│                        │
  │                          │                        │
  │<── ServerInfo + Ticket ──┤                        │
  │                          │                        │
  ├── Connecter au serveur ───────────────────────────>│
  │                          │                        │
  │<── Room ready ────────────────────────────────────┤
```

### Parties personnalisées (CustomBattle)

```
Client                    Photon
  │                         │
  ├─ Créer Room (PUN) ────>│
  │  (nom, maxPlayers,     │
  │   gameMode, bots)      │
  │<── Room créée ─────────┤
  │                         │
  ├─ Inviter amis ────────>│
  │  (via chat/social)     │
  │                         │
  ├─ Démarrer partie ─────>│
  │  (start)               │
```

## Paramètres CustomBattle

| Paramètre | Valeurs possibles |
|-----------|-------------------|
| `GameMode` | Solo, Duo, Squad |
| `BotsEnabled` | true/false |
| `BotsDisabled` | true/false |
| `MaxPlayers` | 1-100 |
| `RoomName` | string |

## États du match

Basé sur les chaînes trouvées :

```
Phase d'attente (SelectArea)
  │
Zone de jeu sélectionnée
  │
Combat démarré
  │
Combat terminé (Death)
  │
KnockDown -> peut être relevé
  │
Mort définitive
  │
Victoire (Combat_Win)
```

## Système de régions

Le jeu utilise la détection de régions Photon :
```
Call ConnectToNameServer to ping available regions.
Waiting for AvailableRegions.
PhotonNetwork.networkingPeer.AvailableRegions
```

Le jeu vérifie :
- `ProtocolServerPort` - Port personnalisé
- `ping_nodes` - Noeuds de ping
