# Systèmes de gameplay

## Quantum Framework (ECS)

Le jeu utilise un framework ECS (Entity Component System) propriétaire appelé **Quantum**.

### Systèmes d'acteurs (Actor)

| Système | Fonction |
|---------|----------|
| `ActorMovementSystem` | Mouvement du joueur |
| `ActorHealthSystem` | Santé, dégâts, mort |
| `ActorDownedDamageSystem` | Dégâts en état "downed" |
| `ActorDownedEventSystem` | Événements downed |
| `ActorReviveSystem` | Réanimation |
| `ActorKillStreakSystem` | Séries de kills |
| `ActorStealthSystem` | Furtivité (buissons ?) |
| `ActorBuildingSystem` | Construction (?) |
| `ActorBotSystem` | Comportement des bots |
| `ActorPlayerInputSystem` | Entrées joueur |
| `ActorView` | Rendu visuel de l'acteur |
| `ActorViewManager` | Gestionnaire des vues |
| `ActorViewAction` | Actions visuelles |

### Systèmes de combat

| Système | Fonction |
|---------|----------|
| `CombatController` | Contrôleur de combat principal |
| `Combat_Kill` | Gestion des kills |
| `Combat_KnockDown` | Gestion des knock down |
| `Combat_Death` | Gestion des morts |
| `Combat_Pickup` | Gestion des pickups |
| `Combat_Started` | Début du combat |
| `Combat_Win` | Victoire |

### Armes (WeaponData)

| Type | Fichier |
|------|---------|
| `WeaponDataMelee` | Armes de mêlée |
| `WeaponDataRanged` | Armes à distance |

### Projectiles

| Type | Fichier |
|------|---------|
| `ProjectileDataDynamic` | Projectiles dynamiques (avec physique) |
| `ProjectileDataKinematic` | Projectiles cinématiques |

### Consommables

| Type | Description |
|------|-------------|
| `ConsumableDataArmor` | Armure |
| `ConsumableDataHealth` | Soin |
| `ConsumableDataRandomItem` | Item aléatoire |
| `ConsumableDataAreaEffect` | Effet de zone |
| `ConsumableDataStatusEffect` | Effet de statut |

### Effets de zone (AreaEffectData)

| Type | Description |
|------|-------------|
| `AreaEffectDataAmmoOverTime` | Munitions sur la durée |
| `AreaEffectDataArmorOverTime` | Armure sur la durée |
| `AreaEffectDataHealthOverTime` | Soin sur la durée |
| `AreaEffectDataDamageOverTime` | Dégâts sur la durée |
| `AreaEffectDataSpeed` | Vitesse |
| `AreaEffectDataStatusEffect` | Effet de statut |

### Effets de statut

| Type | Description |
|------|-------------|
| `StatusEffectDataArmorAndHealthOverTime` | Armure + Soin durée |
| `StatusEffectDataArmorOverTime` | Armure durée |
| `StatusEffectDataHealthOverTime` | Soin durée |
| `StatusEffectDataQuickBush` | Buisson rapide |
| `StatusEffectDataSpeed` | Vitesse |
| `StatusEffectDataStormMultiplier` | Multiplicateur tempête |

### Pickups

| Type | Description |
|------|-------------|
| `PickupDataAmmo` | Munitions |
| `PickupDataArmor` | Armure |
| `PickupDataConsumable` | Consommable |
| `PickupDataDogTag` | DogTag (butin spécial) |
| `PickupDataHealth` | Santé |
| `PickupDataStatusEffect` | Effet de statut |
| `PickupDataSupplyCrate` | Caisse de ravitaillement |
| `PickupDataWeapon` | Arme |

### Autres systèmes

| Système | Description |
|---------|-------------|
| `AimAssistConfig` | Configuration d'aide à la visée |
| `AimHelper` | Aide à la visée |
| `RingOfDeathData` | Zone de tempête/anneau de mort |
| `BuildingData` | Données de construction |
| `Map` | Carte |
| `MapLocationData` | Points d'intérêt sur la carte |
| `UserColliderData` | Colliders utilisateur |
| `UserMapData` | Données carto utilisateur |
| `NavMeshAsset` | Navigation (mesh) |

## Économie

### Monnaies virtuelles

| Devise | Usage |
|--------|-------|
| BattleBucks (`battlebucks`) | Devise premium |
| Gems (`gems`) | Gemmes |
| XP | Points d'expérience |
| DogTags | Tags de chien (monnaie d'événement ?) |
| MatchBoxTokens | Tickets de boîte de match |
| TrophyRewards | Récompenses de trophée |
| SeasonStats | Statistiques de saison |

### Boutiques

| Shop | Contenu |
|------|---------|
| `UIBoxShop` | Coffres (Battle Chest, Premium, Lucky) |
| `SkinShop` | Skins |
| `BattleChestPremium` | Coffre premium |
| `UIBattlebucksShopItem` | Achat de BattleBucks |
| `BattlePass` | Pass de combat |
| `SeasonalBundle` | Bundle saisonnier |

### Saison

Le jeu utilise un système de saisons :
- `startSeason` - Début de saison
- `SeasonEndTimes` - Fin de saison
- `SeasonStatsHistory` - Historique des stats
- `skipBattlePassLevel` - Passer un niveau de pass
- `claimBattlePassReward` - Réclamer récompense pass
- `BattlePassState` - État du pass
- `levelUpSkin` - Skin de level up

### Coffres

| Type | Description |
|------|-------------|
| `BattleChest` | Coffre standard |
| `BattleChestPremium` | Coffre premium |
| `LuckyChest` | Coffre chance |
| `ChestPool` | Pool de coffres |
| `Preview Popup Items` | Aperçu des items |

### Défis / Quêtes

- `ChallengeReward` - Récompense de défi
- `TrophyRoadReward` - Récompense route des trophées
- `DailyFreeItem` - Item gratuit quotidien
- `MatchReportRewards` - Récompenses de match
- `EventRewards` - Récompenses d'événement
- `InboxMessageStates` - Messages en boîte
