# Formats de sérialisation

## JSON (Newtonsoft.Json)

Utilisé pour :
- Toutes les requêtes/réponses PlayFab REST API
- Données de configuration (Firebase Remote Config)
- Catalogue IAP
- Certaines données utilisateur sérialisées
- Événements analytics

Exemple de formats JSON trouvés :
```json
{"screenshot":"{0}","screenname":"{0}","view":[{0}]}
{"message":"{0}"}
{"pfId":"{0}","i":"{1}"}
{"state":"{0}","photon":"{1}"}
{"selected":"{0}","id":"{1}"}
```

## Protocole binaire Photon

Utilisé pour la communication temps réel avec le Photon Cloud :
- Format binaire propriétaire d'Exit Games
- Basé sur des commandes (OperationRequest, OperationResponse)
- Supporte la compression GZIP
- Gère l'encryption automatiquement
- Types : Boolean, Byte, Short, Integer, Long, Float, Double, String, Hashtable, Tableau, etc.

## Sérialisation Quantum

Le framework Quantum a sa propre sérialisation pour les données d'état de jeu :
- `ActorPhotonDataSerialize` - Sérialisation des données d'acteur via Photon
- `OnPhotonSerializeView` - Appelé pour synchroniser les vues Photon
- Utilise `PhotonStream` pour lire/écrire les données

## PlayerPrefs (Unity)

Stockage local de données simples :
- Tokens de session
- Préférences utilisateur
- Identifiants

## Fichiers locaux

| Fichier | Format | Contenu |
|---------|--------|---------|
| `/customid.txt` | Texte | Custom ID PlayFab |
| `/pfid.txt` | Texte | PlayFab ID |

## Pas de Protobuf / FlatBuffers / MessagePack

Aucune référence à ces formats n'a été trouvée dans le binaire. La sérialisation se fait via :
1. JSON (Newtonsoft) pour REST
2. Binaire Photon custom pour temps réel
3. Quantum custom serialize pour l'état de jeu synchrone

## Authentication State

Le jeu utilise une classe `AuthorizationState` pour gérer l'état de l'authentification.
