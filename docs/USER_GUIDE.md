# 📖 Guide Utilisateur

Bienvenue dans le **Guide Utilisateur de Jarvis HA Control** ! Ce guide vous explique comment utiliser toutes les fonctionnalités de votre assistant domotique intelligent.

---

## 📋 Table des Matières

- [🚀 Premier Pas](#-premier-pas)
- [💬 Commandes Vocales et Textuelles](#-commandes-vocales-et-textuelles)
- [🌐 Interface Web](#-interface-web)
- [🤖 Fonctionnalités d'Autonomie](#-fonctionnalités-dautonomie)
- [👁️ Vision et Détection](#-vision-et-détection)
- [📊 Monitoring et Diagnostics](#-monitoring-et-diagnostics)
- [🔒 Sécurité et Accès](#-sécurité-et-accès)
- [⚙️ Personnalisation](#-personnalisation)
- [📱 Intégration avec d'Autres Services](#-intégration-avec-dautres-services)
- [🎯 Astuces et Bonnes Pratiques](#-astuces-et-bonnes-pratiques)
- [🐛 Dépannage](#-dépannage)

---

## 🚀 Premier Pas

### 1. Accéder à l'Interface

Après l'installation, vous pouvez accéder à Jarvis HA Control de plusieurs manières :

#### Via l'Interface Web
- Ouvrez votre navigateur
- Allez à l'adresse : `http://[IP_HOME_ASSISTANT]:8099`
- Vous devriez voir le tableau de bord de Jarvis

#### Via Home Assistant
- Dans Home Assistant, allez dans **Paramètres** > **AppDaemon**
- Vous verrez l'état de Jarvis HA Control
- Vous pouvez accéder à l'interface via le lien fourni

#### Via l'API
```bash
curl http://[IP_HOME_ASSISTANT]:8099/api/status
```

### 2. Première Commande

Pour tester que tout fonctionne, essayez une commande simple :

**Via l'interface web** :
- Tapez dans la barre de commande : `"Bonjour"`
- Appuyez sur Entrée

**Via l'API** :
```bash
curl -X POST http://localhost:8099/api/command \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Bonjour", "speak": false}'
```

**Réponse attendue** :
```json
{
  "response": "Bonjour ! Comment puis-je vous aider aujourd'hui ?",
  "actions": []
}
```

### 3. Vérifier le Statut

Pour vérifier que Jarvis est opérationnel :

```bash
curl http://localhost:8099/api/status
```

**Réponse attendue** :
```json
{
  "version": "3.9.0",
  "status": "running",
  "autonomy_enabled": false,
  "autonomy_status": "inactive",
  "websocket_connected": true,
  "last_command": "2026-11-11T15:00:00Z",
  "commands_today": 1,
  "actions_today": 0
}
```

---

## 💬 Commandes Vocales et Textuelles

### Format des Commandes

Jarvis comprend les commandes en **français** (et d'autres langues selon la configuration).

#### Commandes de Base

| Commande | Description | Exemple |
|----------|-------------|---------|
| `Bonjour` | Salutation | "Bonjour Jarvis" |
| `Allumer [entité]` | Allumer une lumière ou un appareil | "Allume la lumière du salon" |
| `Éteindre [entité]` | Éteindre une lumière ou un appareil | "Éteins les lumières de la cuisine" |
| `Ouvrir [entité]` | Ouvrir un volet ou une porte | "Ouvre le volet du salon" |
| `Fermer [entité]` | Fermer un volet ou une porte | "Ferme la porte du garage" |
| `Régler [entité] à [valeur]` | Régler une valeur | "Règle la température à 22 degrés" |
| `Quelle est la température ?` | Demander la température | "Quelle est la température dans le salon ?" |
| `Quel est l'état de [entité] ?` | Demander l'état | "Quel est l'état des lumières ?" |

#### Commandes Avancées

| Commande | Description | Exemple |
|----------|-------------|---------|
| `Active la scène [nom]` | Activer une scène | "Active la scène Bonjour" |
| `Démarre l'aspirateur` | Démarrer l'aspirateur | "Démarre l'aspirateur du salon" |
| `Envoie une notification` | Envoyer une notification | "Envoie une notification à Olivier" |
| `Joue [médias]` | Lire un média | "Joue de la musique" |
| `Régle le volume à [niveau]` | Régler le volume | "Règle le volume à 50%" |

### Commandes avec Paramètres

Vous pouvez inclure des paramètres dans vos commandes :

- **Temps** : "Allume les lumières à 18h"
- **Durée** : "Allume les lumières pendant 1 heure"
- **Température** : "Règle la climatisation à 22°C"
- **Luminosité** : "Règle la lumière à 75%"
- **Couleur** : "Change la lumière en bleu"

### Exemples Concrets

#### 1. Contrôle des Lumières

```
"Allume la lumière du salon"
"Éteins toutes les lumières"
"Règle la lumière du salon à 50%"
"Change la couleur de la lumière en rouge"
"Allume les lumières du salon et de la cuisine"
```

#### 2. Contrôle des Volets

```
"Ouvre tous les volets"
"Ferme le volet du salon"
"Règle le volet à 50%"
"Ouvre les volets du rez-de-chaussée"
```

#### 3. Contrôle de la Climatisation

```
"Règle la température à 22°C"
"Active le mode chauffage"
"Désactive la climatisation"
"Règle la climatisation du salon à 20°C"
```

#### 4. Contrôle des Médias

```
"Joue de la musique"
"Joue la playlist Rock"
"Pause la musique"
"Règle le volume à 75%"
"Mets la musique plus fort"
```

#### 5. Scènes et Automatisations

```
"Active la scène Bonjour"
"Active la scène Nuit"
"Active la scène Cinéma"
"Démarre l'automatisation Nettoyage"
```

### Réponses Vocales

Si la réponse vocale est activée (`auto_speak: true`), Jarvis répondra vocalement à vos commandes.

**Exemple** :
- Vous : "Allume la lumière du salon"
- Jarvis : "J'allume la lumière du salon"

---

## 🌐 Interface Web

L'interface web de Jarvis HA Control offre une expérience utilisateur complète.

### Tableau de Bord

Le tableau de bord est la première page que vous voyez lorsque vous accédez à l'interface. Il affiche :

- **Statut du système** : Version, état, connexion WebSocket
- **Statistiques** : Nombre de commandes et actions aujourd'hui
- **Autonomie** : État de l'autonomie et nombre de règles actives
- **Dernières commandes** : Historique des dernières commandes
- **Alertes** : Alertes et notifications importantes

### Navigation

L'interface est organisée en plusieurs sections :

#### 1. **Commandes**
- Barre de commande pour entrer des commandes textuelles
- Historique des commandes précédentes
- Suggestions de commandes

#### 2. **Autonomie**
- Liste des règles d'autonomie actives
- État de chaque règle
- Historique des actions autonomes
- Journal des décisions

#### 3. **Monitoring**
- Métriques système en temps réel (CPU, mémoire, disque, réseau)
- Graphiques de performance
- Alertes de monitoring
- Historique des métriques

#### 4. **Sécurité**
- Liste des utilisateurs
- Journal des accès
- Audit des actions
- Gestion des sessions

#### 5. **Vision**
- Flux vidéo des caméras (si Frigate est configuré)
- Historique des détections
- Alertes de vision
- Configuration des caméras

#### 6. **Configuration**
- Paramètres généraux
- Configuration de l'API Gemini
- Configuration de la réponse vocale
- Configuration de l'autonomie
- Configuration de la sécurité

### Utilisation de l'Interface

#### 1. Exécuter une Commande

1. Allez dans l'onglet **Commandes**
2. Tapez votre commande dans la barre de texte
3. Appuyez sur **Entrée** ou cliquez sur le bouton **Envoyer**
4. Attendez la réponse de Jarvis

#### 2. Voir l'Historique

1. Allez dans l'onglet **Historique**
2. Vous verrez la liste de toutes les commandes exécutées
3. Vous pouvez filtrer par date, type, ou statut
4. Cliquez sur une commande pour voir les détails

#### 3. Gérer l'Autonomie

1. Allez dans l'onglet **Autonomie**
2. Vous verrez la liste des règles actives
3. Cliquez sur une règle pour la modifier ou la désactiver
4. Ajoutez de nouvelles règles en cliquant sur **Ajouter une règle**

#### 4. Surveiller les Performances

1. Allez dans l'onglet **Monitoring**
2. Vous verrez les métriques système en temps réel
3. Cliquez sur un graphique pour plus de détails
4. Configurez des alertes en cliquant sur **Configurer les alertes**

---

## 🤖 Fonctionnalités d'Autonomie

L'autonomie permet à Jarvis de prendre des décisions et d'exécuter des actions sans votre intervention.

### Activer l'Autonomie

1. Dans `config.yaml`, définissez :
   ```yaml
   options:
     autonomy_enabled: true
   ```

2. Redémarrez Jarvis HA Control

3. Vérifiez que l'autonomie est active :
   ```bash
   curl http://localhost:8099/api/autonomy
   ```

### Règles d'Autonomie

Les règles d'autonomie définissent quand et comment Jarvis doit agir.

#### Exemples de Règles

| Nom | Description | Conditions | Actions |
|-----|-------------|------------|---------|
| `allumer_lumieres_soir` | Allumer les lumières le soir | Il fait nuit + Présence détectée | Allumer les lumières du salon |
| `eteindre_lumieres_nuit` | Éteindre les lumières la nuit | Il est 23h | Éteindre toutes les lumières |
| `fermer_volets_coucher` | Fermer les volets au coucher | Il est 22h30 | Fermer tous les volets |
| `chauffage_matin` | Activer le chauffage le matin | Il est 7h + Température < 19°C | Régler la température à 21°C |

### Créer une Nouvelle Règle

1. Allez dans l'onglet **Autonomie**
2. Cliquez sur **Ajouter une règle**
3. Remplissez les champs :
   - **Nom** : Nom unique de la règle
   - **Description** : Description de ce que fait la règle
   - **Conditions** : Quand la règle doit s'appliquer
   - **Actions** : Quelles actions exécuter
   - **Priorité** : Priorité de la règle (1-10)
4. Sauvegardez la règle

### Conditions

Les conditions définissent quand une règle doit s'appliquer.

#### Types de Conditions

| Type | Description | Exemple |
|------|-------------|---------|
| État d'une entité | L'état d'une entité Home Assistant | `sun.sun == below_horizon` |
| Heure | Une heure spécifique | `time == 18:00` |
| Plage horaire | Une plage d'heures | `time between 18:00 and 23:00` |
| Température | Une température spécifique | `sensor.temperature > 25` |
| Présence | Détection de présence | `binary_sensor.presence == on` |
| Mouvement | Détection de mouvement | `binary_sensor.motion == on` |

#### Opérateurs de Comparaison

- `==` : Égal à
- `!=` : Différent de
- `>` : Supérieur à
- `<` : Inférieur à
- `>=` : Supérieur ou égal à
- `<=` : Inférieur ou égal à

#### Opérateurs Logiques

- `and` : ET logique (toutes les conditions doivent être vraies)
- `or` : OU logique (au moins une condition doit être vraie)
- `not` : NON logique (la condition doit être fausse)

### Actions

Les actions définissent ce que Jarvis doit faire quand une règle est déclenchée.

#### Types d'Actions

| Domaine | Service | Description | Exemple |
|---------|---------|-------------|---------|
| light | turn_on | Allumer une lumière | `light.turn_on(light.living_room)` |
| light | turn_off | Éteindre une lumière | `light.turn_off(light.living_room)` |
| light | toggle | Basculer une lumière | `light.toggle(light.living_room)` |
| cover | open | Ouvrir un volet | `cover.open(cover.garage)` |
| cover | close | Fermer un volet | `cover.close(cover.garage)` |
| climate | set_temperature | Régler la température | `climate.set_temperature(climate.living_room, 22)` |
| vacuum | start | Démarrer l'aspirateur | `vacuum.start(vacuum.robot)` |
| scene | activate | Activer une scène | `scene.activate(scene.good_morning)` |
| notify | mobile_app | Envoyer une notification | `notify.mobile_app("Message")` |

### Exemples de Règles Complètes

#### Règle 1 : Allumer les lumières le soir

```
Nom : allumer_lumieres_soir
Description : Allumer les lumières du salon quand il fait nuit et qu'il y a quelqu'un
Conditions :
  - sun.sun == below_horizon
  - binary_sensor.presence_living_room == on
Actions :
  - light.turn_on(light.living_room)
Priorité : 5
```

#### Règle 2 : Éteindre les lumières la nuit

```
Nom : eteindre_lumieres_nuit
Description : Éteindre toutes les lumières à 23h
Conditions :
  - time == 23:00
Actions :
  - light.turn_off(all)
Priorité : 10
```

#### Règle 3 : Activer le chauffage le matin

```
Nom : chauffage_matin
Description : Activer le chauffage le matin si il fait froid
Conditions :
  - time == 07:00
  - sensor.living_room_temperature < 19
Actions :
  - climate.set_temperature(climate.living_room, 21)
  - climate.set_hvac_mode(climate.living_room, heat)
Priorité : 7
```

### Journal des Actions Autonomes

Toutes les actions exécutées par l'autonomie sont enregistrées dans le journal. Vous pouvez :

1. Voir l'historique des actions autonomes
2. Filtrer par date, règle, ou statut
3. Voir les détails de chaque action
4. Exporter le journal

### Approbation des Actions

Si une action nécessite une approbation, Jarvis vous enverra une notification.

**Exemple** :
- Jarvis détecte qu'il faut ouvrir la porte du garage
- Il envoie une notification : "Souhaitez-vous que j'ouvre la porte du garage ?"
- Vous pouvez approuver ou rejeter l'action

---

## 👁️ Vision et Détection

La vision permet à Jarvis de détecter et de réagir à des événements visuels via Frigate.

### Activer la Vision

1. Dans `config.yaml`, définissez :
   ```yaml
   options:
     vision_enabled: true
     frigate_url: "http://[IP_FRIGATE]:5000"
     vision_labels:
       - person
       - car
     vision_cameras:
       - camera.front_door
   ```

2. Redémarrez Jarvis HA Control

3. Vérifiez que la vision est active :
   ```bash
   curl http://localhost:8099/api/status | grep vision
   ```

### Fonctionnalités de Vision

#### 1. Détection d'Objets

Jarvis peut détecter différents types d'objets :

- **Personnes** : Détection de personnes
- **Véhicules** : Détection de voitures, camions, motos
- **Animaux** : Détection de chiens, chats, oiseaux
- **Objets** : Détection d'autres objets selon votre modèle

#### 2. Alertes de Détection

Quand un objet est détecté, Jarvis peut :

- Envoyer une notification
- Exécuter une action
- Enregistrer l'événement
- Déclencher une règle d'autonomie

**Exemple** :
```
Quand une personne est détectée devant la porte :
- Envoyer une notification : "Personne détectée devant la porte"
- Allumer la lumière extérieure
- Activer l'enregistrement vidéo
```

#### 3. Flux Vidéo en Direct

Vous pouvez voir les flux vidéo des caméras directement dans l'interface web :

1. Allez dans l'onglet **Vision**
2. Sélectionnez une caméra
3. Vous verrez le flux vidéo en direct
4. Vous pouvez voir l'historique des détections

#### 4. Historique des Détections

Toutes les détections sont enregistrées et vous pouvez :

- Voir l'historique des détections
- Filtrer par caméra, type d'objet, ou date
- Exporter l'historique
- Configurer des alertes

### Configuration des Caméras

1. Allez dans l'onglet **Vision**
2. Cliquez sur **Configurer les caméras**
3. Ajoutez vos caméras :
   - **Nom** : Nom de la caméra
   - **URL** : URL du flux vidéo
   - **Étiquettes** : Types d'objets à détecter
   - **Zone** : Zone de détection
4. Sauvegardez la configuration

### Exemple de Configuration Frigate

```yaml
# frigate/config.yml
mqtt:
  host: 192.168.1.100

detectors:
  - name: front_door
    type: cpu
    
cameras:
  front_door:
    ffmpeg:
      inputs:
        - path: rtsp://192.168.1.200:554/stream
          roles:
            - detect
    detect:
      width: 1280
      height: 720
      fps: 5
    
  backyard:
    ffmpeg:
      inputs:
        - path: rtsp://192.168.1.201:554/stream
          roles:
            - detect
    detect:
      width: 1280
      height: 720
      fps: 5
```

---

## 📊 Monitoring et Diagnostics

Le monitoring permet de surveiller les performances de votre système et de Jarvis.

### Tableau de Bord de Monitoring

1. Allez dans l'onglet **Monitoring**
2. Vous verrez :
   - **Métriques système** : CPU, mémoire, disque, réseau
   - **Métriques Jarvis** : Temps de réponse, nombre de commandes
   - **Alertes** : Alertes actives
   - **Graphiques** : Historique des métriques

### Métriques Système

| Métrique | Description | Unité |
|----------|-------------|-------|
| CPU Usage | Utilisation du CPU | % |
| Memory Usage | Utilisation de la mémoire | % |
| Disk Usage | Utilisation du disque | % |
| Network I/O | Trafic réseau | Bytes |
| Temperature | Température du système | °C |

### Métriques Jarvis

| Métrique | Description | Unité |
|----------|-------------|-------|
| Response Time | Temps de réponse moyen | ms |
| Commands/Minute | Nombre de commandes par minute | cmd/min |
| Actions/Minute | Nombre d'actions par minute | act/min |
| Cache Hit Rate | Taux de succès du cache | % |
| Error Rate | Taux d'erreurs | % |

### Alertes

Les alertes sont déclenchées quand une métrique dépasse un seuil.

#### Types d'Alertes

| Type | Description | Seuil par défaut |
|------|-------------|-------------------|
| CPU High | Utilisation CPU élevée | > 80% |
| Memory High | Utilisation mémoire élevée | > 80% |
| Disk Full | Disque presque plein | > 90% |
| Slow Response | Temps de réponse élevé | > 1000ms |
| High Error Rate | Taux d'erreurs élevé | > 5% |

#### Configurer une Alerte

1. Allez dans l'onglet **Monitoring**
2. Cliquez sur **Configurer les alertes**
3. Ajoutez une nouvelle alerte :
   - **Nom** : Nom de l'alerte
   - **Métrique** : Métrique à surveiller
   - **Seuil** : Valeur seuil
   - **Opérateur** : >, <, ==, >=, <=, !=
   - **Durée** : Durée avant de déclencher l'alerte
   - **Actions** : Actions à exécuter quand l'alerte est déclenchée
4. Sauvegardez l'alerte

### Journal des Événements

Tous les événements sont enregistrés dans le journal :

1. Allez dans l'onglet **Journal**
2. Vous verrez :
   - **Événements système** : Démarrage, arrêt, erreurs
   - **Commandes** : Toutes les commandes exécutées
   - **Actions** : Toutes les actions exécutées
   - **Alertes** : Toutes les alertes déclenchées
3. Vous pouvez filtrer par type, date, ou niveau de gravité

### Diagnostic Système

Pour obtenir un diagnostic complet du système :

```bash
curl http://localhost:8099/api/diagnostic
```

**Réponse** :
```json
{
  "system": {
    "cpu_usage": 45.2,
    "memory_usage": 62.8,
    "disk_usage": 34.5,
    "network_io": {
      "sent": 1024,
      "received": 2048
    }
  },
  "jarvis": {
    "version": "3.9.0",
    "status": "running",
    "uptime": "2h 30m",
    "commands_today": 42,
    "actions_today": 25,
    "response_time_avg": 150,
    "error_rate": 0.0
  },
  "autonomy": {
    "enabled": true,
    "rules_count": 5,
    "actions_today": 12
  },
  "performance": {
    "cache_hit_rate": 0.85,
    "batch_processing": {
      "items_processed": 100,
      "batches_completed": 10
    }
  }
}
```

---

## 🔒 Sécurité et Accès

### Gestion des Utilisateurs

Jarvis HA Control supporte plusieurs utilisateurs avec différents niveaux d'accès.

#### Rôles

| Rôle | Permissions | Description |
|------|-------------|-------------|
| `admin` | Lecture, Écriture, Exécution, Configuration | Accès complet |
| `user` | Lecture, Écriture, Exécution | Accès aux commandes |
| `guest` | Lecture | Accès en lecture seule |

#### Ajouter un Utilisateur

1. Allez dans l'onglet **Sécurité**
2. Cliquez sur **Ajouter un utilisateur**
3. Remplissez les champs :
   - **Nom d'utilisateur** : Nom unique
   - **Mot de passe** : Mot de passe sécurisé
   - **Rôle** : admin, user, ou guest
   - **Permissions** : Permissions spécifiques (optionnel)
4. Sauvegardez l'utilisateur

### Authentification

#### Authentification de Base

Par défaut, Jarvis utilise l'authentification de Home Assistant.

#### Authentification Vocale

Si la voix est activée avec un code PIN :

1. L'utilisateur dit : "Jarvis, code 1234"
2. Jarvis vérifie le code PIN
3. Si le code est correct, l'utilisateur peut exécuter des commandes

### Journal d'Audit

Toutes les actions sont enregistrées dans le journal d'audit :

1. Allez dans l'onglet **Sécurité**
2. Cliquez sur **Journal d'audit**
3. Vous verrez :
   - **Connexions** : Toutes les connexions
   - **Commandes** : Toutes les commandes exécutées
   - **Actions** : Toutes les actions exécutées
   - **Modifications** : Toutes les modifications de configuration
4. Vous pouvez filtrer par utilisateur, date, ou type d'action

### Gestion des Sessions

Les sessions utilisateurs sont gérées automatiquement :

- **Timeout** : Les sessions expirent après 1 heure d'inactivité
- **Invalidation** : Les sessions peuvent être invalidées manuellement
- **Connexions multiples** : Un utilisateur peut avoir plusieurs sessions

### Sécurité des Données

Jarvis HA Control prend la sécurité des données au sérieux :

- **Chiffrement** : Toutes les communications sont chiffrées
- **Stockage sécurisé** : Les données sensibles sont stockées de manière sécurisée
- **Accès contrôlé** : L'accès est contrôlé par des rôles et permissions
- **Audit complet** : Toutes les actions sont enregistrées et auditées

---

## ⚙️ Personnalisation

### Personnaliser les Prompts

Vous pouvez personnaliser les prompts utilisés par Jarvis pour générer des réponses.

1. Éditez le fichier `app/assistant/prompts.py`
2. Modifiez les prompts selon vos besoins
3. Redémarrez Jarvis

**Exemple de prompt personnalisé** :

```python
SYSTEM_PROMPT = """
Tu es Jarvis, un assistant domotique intelligent pour Home Assistant.
Ton rôle est d'aider l'utilisateur à contrôler sa maison de manière naturelle et intuitive.

Règles :
1. Réponds toujours en français
2. Sois concis et direct
3. Si tu ne comprends pas, demande des clarifications
4. Ne fais pas d'hypothèses sur les entités disponibles
5. Utilise toujours les outils disponibles pour exécuter des actions

Exemples de commandes :
- "Allume la lumière du salon"
- "Quelle est la température dans la cuisine ?"
- "Active la scène Bonjour"
"""
```

### Personnaliser les Règles d'Autonomie

Vous pouvez créer des règles d'autonomie personnalisées :

1. Éditez le fichier `app/autonomy/rules.py`
2. Ajoutez vos règles personnalisées
3. Redémarrez Jarvis

**Exemple de règle personnalisée** :

```python
from jarvis_ha_control.app.autonomy.rules import Rule, Condition, Action

# Règle personnalisée : Allumer les lumières quand il pleut
RAIN_LIGHTS_RULE = Rule(
    name="allumer_lumieres_pluie",
    description="Allumer les lumières quand il pleut et qu'il fait sombre",
    conditions=[
        Condition(entity="weather.home", state="rainy"),
        Condition(entity="sun.sun", state="below_horizon"),
        Condition(entity="binary_sensor.presence_living_room", state="on")
    ],
    actions=[
        Action(domain="light", service="turn_on", entity_id="light.living_room"),
        Action(domain="light", service="turn_on", entity_id="light.kitchen")
    ],
    priority=8
)

# Ajouter la règle à la liste des règles
RULES = [
    RAIN_LIGHTS_RULE,
    # ... autres règles
]
```

### Personnaliser l'Interface Web

Vous pouvez personnaliser l'interface web :

1. Modifiez les fichiers dans le dossier `webui/`
2. Redémarrez Jarvis

**Structure du dossier webui** :
```
webui/
├── index.html          # Page principale
├── styles.css          # Styles CSS
├── app.js              # JavaScript principal
├── dashboard.js        # Tableau de bord
├── commands.js         # Gestion des commandes
├── autonomy.js         # Gestion de l'autonomie
├── monitoring.js       # Monitoring
├── security.js         # Sécurité
└── vision.js           # Vision
```

### Personnaliser les Actions

Vous pouvez créer des actions personnalisées :

1. Éditez le fichier `app/tools/actions.py`
2. Ajoutez vos actions personnalisées
3. Redémarrez Jarvis

**Exemple d'action personnalisée** :

```python
async def my_custom_action(entity_id, **kwargs):
    """Action personnalisée."""
    # Faire quelque chose
    logger.info(f"Exécution de l'action personnalisée sur {entity_id}")
    
    # Retourner le résultat
    return {
        "status": "success",
        "message": f"Action personnalisée exécutée sur {entity_id}"
    }

# Enregistrer l'action
ACTION_HANDLERS["my_custom_action"] = my_custom_action
```

---

## 📱 Intégration avec d'Autres Services

### Intégration avec Home Assistant

Jarvis HA Control est conçu pour fonctionner parfaitement avec Home Assistant.

#### Services Disponibles

| Service | Description | Exemple |
|---------|-------------|---------|
| `jarvis.command` | Exécuter une commande | `service: jarvis.command, data: {prompt: "Allume la lumière"}` |
| `jarvis.speak` | Synthèse vocale | `service: jarvis.speak, data: {text: "Bonjour"}` |
| `jarvis.notify` | Envoyer une notification | `service: jarvis.notify, data: {message: "Alert"}` |

#### Automatisations

**Exemple 1 : Automatisation avec Jarvis**

```yaml
automation:
  - alias: "Demander à Jarvis le matin"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: jarvis.command
        data:
          prompt: "Bonjour, quelle est la météo aujourd'hui ?"
          speak: true
```

**Exemple 2 : Automatisation avec détection de présence**

```yaml
automation:
  - alias: "Allumer les lumières avec Jarvis"
    trigger:
      - platform: state
        entity_id: binary_sensor.presence_living_room
        to: "on"
    action:
      - service: jarvis.command
        data:
          prompt: "Allume la lumière du salon"
```

### Intégration avec Frigate

Jarvis peut s'intégrer avec Frigate pour la détection visuelle.

**Exemple : Automatisation avec détection de personne**

```yaml
automation:
  - alias: "Notification de détection de personne"
    trigger:
      - platform: mqtt
        topic: "frigate/events"
        payload: "person"
    action:
      - service: jarvis.command
        data:
          prompt: "Une personne a été détectée devant la porte"
          speak: true
```

### Intégration avec d'Autres Services

#### 1. Intégration avec Telegram

```yaml
# configuration.yaml
telegram_bot:
  - platform: polling
    api_key: YOUR_TELEGRAM_API_KEY
    allowed_chat_ids:
      - 123456789

# automation.yaml
automation:
  - alias: "Envoyer un message Telegram via Jarvis"
    trigger:
      - platform: event
        event_type: jarvis_notify
    action:
      - service: telegram_bot.send_message
        data:
          target: 123456789
          message: "{{ trigger.event.data.message }}"
```

#### 2. Intégration avec Discord

```yaml
# configuration.yaml
discord:
  webhook_id: YOUR_WEBHOOK_ID
  webhook_token: YOUR_WEBHOOK_TOKEN

# automation.yaml
automation:
  - alias: "Envoyer un message Discord via Jarvis"
    trigger:
      - platform: event
        event_type: jarvis_notify
    action:
      - service: discord.send_message
        data:
          message: "{{ trigger.event.data.message }}"
```

#### 3. Intégration avec Google Assistant

Utilisez l'intégration **Home Assistant Cloud** ou **Nabu Casa** pour connecter Jarvis à Google Assistant.

#### 4. Intégration avec Alexa

Utilisez l'intégration **Alexa Media Player** ou **Hass.io Alexa** pour connecter Jarvis à Alexa.

---

## 🎯 Astuces et Bonnes Pratiques

### Optimisation des Performances

1. **Activez le cache** : Le cache réduit le nombre de requêtes à l'API
   ```yaml
   CACHE_ENABLED: true
   ```

2. **Utilisez le traitement par lots** : Le batch processing permet d'exécuter plusieurs actions en parallèle
   ```yaml
   BATCH_PROCESSING_ENABLED: true
   ```

3. **Activez le monitoring** : Le monitoring vous aide à identifier les goulots d'étranglement
   ```yaml
   PERFORMANCE_MONITORING_ENABLED: true
   ```

4. **Limitez les règles d'autonomie** : Trop de règles actives peuvent ralentir le système

5. **Utilisez des intervalles adaptatifs** : Réduisez l'intervalle de polling quand l'activité est faible

### Sécurité

1. **Utilisez des tokens sécurisés** : Ne partagez jamais votre token Home Assistant

2. **Activez l'authentification à deux facteurs** : Pour l'accès à l'interface web

3. **Limitez les permissions** : Donnez uniquement les permissions nécessaires aux utilisateurs

4. **Mettez à jour régulièrement** : Gardez Jarvis à jour avec les dernières versions

5. **Sauvegardez votre configuration** : Sauvegardez régulièrement votre fichier `config.yaml`

### Gestion des Erreurs

1. **Vérifiez les logs** : Les logs contiennent des informations précieuses pour le dépannage
   ```bash
   tail -f /config/appdaemon/logs/appdaemon.log
   ```

2. **Utilisez le diagnostic** : Le diagnostic système peut aider à identifier les problèmes
   ```bash
   curl http://localhost:8099/api/diagnostic
   ```

3. **Testez les commandes** : Testez toujours les commandes dans un environnement sûr avant de les déployer

4. **Utilisez le fallback** : Jarvis utilise automatiquement le modèle de secours en cas d'échec

5. **Configurez des alertes** : Configurez des alertes pour être notifié en cas de problème

### Commandes Utiles

| Commande | Description |
|----------|-------------|
| `/api/status` | Vérifier le statut |
| `/api/diagnostic` | Obtenir un diagnostic complet |
| `/api/version` | Vérifier la version |
| `/api/version/check` | Vérifier les mises à jour |
| `/api/autonomy` | Vérifier l'autonomie |
| `/api/proposals` | Voir les propositions |
| `/api/journal` | Voir le journal |

---

## 🐛 Dépannage

### Problèmes Courants

#### 1. Jarvis ne répond pas

**Symptômes** :
- Les commandes ne sont pas exécutées
- Pas de réponse de Jarvis

**Solutions** :
- Vérifiez que Jarvis est en cours d'exécution : `curl http://localhost:8099/api/status`
- Vérifiez les logs : `tail -f /config/appdaemon/logs/appdaemon.log`
- Vérifiez la connexion à l'API Gemini
- Vérifiez la connexion à Home Assistant

#### 2. Erreur de connexion à l'API Gemini

**Symptômes** :
```
GeminiUnavailable: Failed to connect to Gemini API
```

**Solutions** :
- Vérifiez que votre clé API est correcte
- Vérifiez que vous avez du crédit sur votre compte Google Cloud
- Vérifiez que votre réseau autorise les connexions vers `generativelanguage.googleapis.com`
- Essayez avec le modèle de secours

#### 3. Erreur de connexion à Home Assistant

**Symptômes** :
```
Failed to connect to Home Assistant API
```

**Solutions** :
- Vérifiez que l'URL de Home Assistant est correcte
- Vérifiez que le token est valide
- Vérifiez que Home Assistant est en cours d'exécution
- Vérifiez que le port est ouvert

#### 4. Les actions ne sont pas exécutées

**Symptômes** :
- Jarvis répond mais les actions ne sont pas exécutées
- Les lumières ne s'allument pas

**Solutions** :
- Vérifiez que `actions_enabled: true` dans `config.yaml`
- Vérifiez que les domaines sont autorisés dans `allowed_domains`
- Vérifiez que les entités existent dans Home Assistant
- Vérifiez les permissions de l'utilisateur

#### 5. L'autonomie ne fonctionne pas

**Symptômes** :
- Les règles d'autonomie ne sont pas déclenchées
- Aucune action autonome n'est exécutée

**Solutions** :
- Vérifiez que `autonomy_enabled: true` dans `config.yaml`
- Vérifiez que les règles sont activées
- Vérifiez que les conditions sont correctes
- Vérifiez les logs pour les erreurs

#### 6. Problèmes de performance

**Symptômes** :
- Latence élevée
- Utilisation CPU/mémoire élevée

**Solutions** :
- Activez le monitoring : `PERFORMANCE_MONITORING_ENABLED: true`
- Vérifiez les métriques : `curl http://localhost:8099/api/diagnostics`
- Réduisez le nombre de règles d'autonomie actives
- Ajustez les paramètres de cache et de batch processing

#### 7. Problèmes de vision

**Symptômes** :
- La détection visuelle ne fonctionne pas
- Aucune détection dans Frigate

**Solutions** :
- Vérifiez que `vision_enabled: true` dans `config.yaml`
- Vérifiez que Frigate est en cours d'exécution
- Vérifiez que l'URL de Frigate est correcte
- Vérifiez que les caméras sont configurées
- Vérifiez les logs de Frigate

#### 8. Problèmes de mise à jour

**Symptômes** :
- Les mises à jour ne sont pas détectées
- `/api/version/check` retourne toujours "up_to_date"

**Solutions** :
- Vérifiez votre connexion Internet
- Vérifiez que l'API GitHub est accessible
- Essayez de forcer le rafraîchissement du cache
- Vérifiez que vous utilisez la dernière version

---

## 📚 Ressources Supplémentaires

- [Documentation Technique](TECHNICAL.md)
- [Guide d'Installation](INSTALLATION.md)
- [Guide de Configuration](CONFIGURATION.md)
- [API Reference](API_REFERENCE.md)
- [Architecture](ARCHITECTURE.md)

---

## 🙏 Support

Si vous rencontrez des problèmes qui ne sont pas couverts par ce guide :

- **GitHub Issues** : [https://github.com/atila593/jarvis-ha-control/issues](https://github.com/atila593/jarvis-ha-control/issues)
- **Discussions** : [https://github.com/atila593/jarvis-ha-control/discussions](https://github.com/atila593/jarvis-ha-control/discussions)
- **Email** : boucaolivier@gmail.com

---

**Bonne utilisation de Jarvis HA Control ! 🎉**
