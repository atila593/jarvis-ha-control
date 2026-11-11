# ⚙️ Guide de Configuration

Ce guide vous explique comment configurer Jarvis HA Control pour répondre à vos besoins spécifiques.

---

## 📋 Table des Matières

- [📝 Fichier de Configuration Principal](#-fichier-de-configuration-principal)
- [🔑 Configuration de l'API Gemini](#-configuration-de-lapi-gemini)
- [🎤 Configuration de la Réponse Vocale](#-configuration-de-la-réponse-vocale)
- [⚡ Configuration des Actions](#-configuration-des-actions)
- [🤖 Configuration de l'Autonomie](#-configuration-de-lautonomie)
- [👤 Configuration de la Sécurité](#-configuration-de-la-sécurité)
- [👁️ Configuration de la Vision (Frigate)](#-configuration-de-la-vision-frigate)
- [📊 Configuration du Monitoring](#-configuration-du-monitoring)
- [🔄 Configuration des Mises à Jour](#-configuration-des-mises-à-jour)
- [📌 Configuration Avancée](#-configuration-avancée)
- [✅ Validation de la Configuration](#-validation-de-la-configuration)

---

## 📝 Fichier de Configuration Principal

Le fichier de configuration principal est `config.yaml`. Il contient tous les paramètres nécessaires pour faire fonctionner Jarvis HA Control.

### Structure de Base

```yaml
name: Jarvis HA Control
version: "3.9.0"
slug: jarvis_ha_control
description: "Assistant Gemini, HUD web et diagnostic systeme pour Home Assistant"
url: https://github.com/atila593/jarvis-ha-control
arch:
  - amd64
  - aarch64
startup: application
boot: auto
init: false
ingress: true
ingress_port: 8099
panel_icon: mdi:robot-outline
panel_title: Jarvis
homeassistant_api: true
hassio_api: true
```

### Section `options`

La section `options` contient tous les paramètres configurables :

```yaml
options:
  # API Gemini
  gemini_api_key: ""
  gemini_model: gemini-3.6-flash
  gemini_fallback_model: gemini-3.5-flash
  
  # Réponse vocale
  speak_service: ""
  speak_targets: []
  auto_speak: false
  speak_tts_platform: "tts.piper"
  speak_language: "fr_FR"
  speak_voice: "fr_FR-tom-medium"
  
  # Actions
  actions_enabled: true
  allowed_domains:
    - light
    - cover
    - vacuum
    - scene
  action_entities: []
  
  # Autonomie
  autonomy_enabled: false
  autonomy_interval: 30
  autonomy_rules: []
  auto_rules: []
  approvers: []
  
  # Présence
  presence_prefix: ""
  presence_zone_names: []
  
  # Disponibilité
  quiet_start: "23:00"
  quiet_end: "07:00"
  unavailable_minutes: 30
  
  # Ingénieur
  engineer_enabled: false
  engineer_edit_existing: false
  stale_days: 7
  
  # Vision
  vision_enabled: false
  frigate_url: ""
  vision_labels:
    - person
  vision_cameras: []
  vision_api_key: ""
  vision_model: ""
  vision_daily_budget: 60
  vision_cooldown_minutes: 5
  
  # Mémoire et Voix
  memory_enabled: false
  voice_enabled: false
  voice_pin: ""
  user_roles: []
  
  # Rapports
  notify_service: ""
  daily_report_time: ""
  proposal_ttl_minutes: 120
```

---

## 🔑 Configuration de l'API Gemini

L'API Gemini est le cœur de Jarvis HA Control. Elle permet à l'assistant de comprendre et de générer des réponses intelligentes.

### Paramètres

| Paramètre | Type | Description | Valeur par défaut | Requis |
|-----------|------|-------------|-------------------|--------|
| `gemini_api_key` | string | Clé API pour accéder à l'API Gemini | `""` | ✅ Oui |
| `gemini_model` | string | Modèle principal à utiliser | `gemini-3.6-flash` | ❌ Non |
| `gemini_fallback_model` | string | Modèle de secours en cas d'échec | `gemini-3.5-flash` | ❌ Non |

### Comment obtenir une clé API

1. Allez sur [Google AI Studio](https://aistudio.google.com/)
2. Créez un nouveau projet ou sélectionnez-en un existant
3. Allez dans **API Keys**
4. Générez une nouvelle clé API
5. Copiez la clé dans `gemini_api_key`

### Modèles disponibles

- `gemini-3.6-flash` : Modèle le plus récent et le plus performant
- `gemini-3.5-flash` : Modèle de secours, légèrement moins performant
- `gemini-3-pro` : Modèle Pro (payant)
- `gemini-2.5-flash` : Modèle plus ancien mais stable

### Exemple de Configuration

```yaml
options:
  gemini_api_key: "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ123456"
  gemini_model: gemini-3.6-flash
  gemini_fallback_model: gemini-3.5-flash
```

### Gestion des Quotas

L'API Gemini a des quotas de requêtes. Voici quelques conseils :

1. **Quotas gratuits** : 15 requêtes/minute, 1000 requêtes/jour
2. **Quotas payants** : Dépendent de votre abonnement
3. **Gestion des erreurs** : Jarvis utilise automatiquement le fallback en cas de quota dépassé
4. **Optimisation** : Activez le cache pour réduire le nombre de requêtes

---

## 🎤 Configuration de la Réponse Vocale

Jarvis HA Control peut répondre vocalement à vos commandes.

### Paramètres

| Paramètre | Type | Description | Valeur par défaut | Requis |
|-----------|------|-------------|-------------------|--------|
| `speak_service` | string | Service Home Assistant pour la parole | `""` | ❌ Non |
| `speak_targets` | list | Cibles pour la parole (entités) | `[]` | ❌ Non |
| `auto_speak` | boolean | Répondre automatiquement vocalement | `false` | ❌ Non |
| `speak_tts_platform` | string | Plateforme TTS à utiliser | `tts.piper` | ❌ Non |
| `speak_language` | string | Langue pour la synthèse vocale | `fr_FR` | ❌ Non |
| `speak_voice` | string | Voix à utiliser | `fr_FR-tom-medium` | ❌ Non |

### Exemple de Configuration

```yaml
options:
  speak_service: "notify.mobile_app"
  speak_targets:
    - "phone_olivier"
    - "phone_marie"
  auto_speak: true
  speak_tts_platform: "tts.piper"
  speak_language: "fr_FR"
  speak_voice: "fr_FR-tom-medium"
```

### Plateformes TTS Supportées

- **Piper** : `tts.piper` (recommandé pour le français)
- **Google TTS** : `tts.google_translate`
- **Microsoft TTS** : `tts.microsoft`
- **Amazon Polly** : `tts.amazon_polly`
- **Picovoice** : `tts.picovoice`

### Voix Disponibles (Piper)

- Français : `fr_FR-tom-medium`, `fr_FR-apope-low`, `fr_FR-gilles-low`
- Anglais : `en_US-kathleen-low`, `en_US-ryan-medium`, `en_US-john-low`
- Espagnol : `es_ES-dave-medium`, `es_ES-laura-medium`
- Allemand : `de_DE-kerstin-medium`, `de_DE-pavoque-medium`

### Configuration Avancée

Pour utiliser un service de notification personnalisé :

```yaml
options:
  speak_service: "notify.my_custom_service"
  speak_targets:
    - "my_device"
  auto_speak: true
```

---

## ⚡ Configuration des Actions

Les actions permettent à Jarvis d'interagir avec votre système domotique.

### Paramètres

| Paramètre | Type | Description | Valeur par défaut | Requis |
|-----------|------|-------------|-------------------|--------|
| `actions_enabled` | boolean | Activer les actions | `true` | ❌ Non |
| `allowed_domains` | list | Domaines autorisés pour les actions | `[light, cover, vacuum, scene]` | ❌ Non |
| `action_entities` | list | Entités spécifiques autorisées | `[]` | ❌ Non |

### Exemple de Configuration

```yaml
options:
  actions_enabled: true
  allowed_domains:
    - light
    - cover
    - vacuum
    - scene
    - switch
    - climate
    - media_player
  action_entities:
    - light.living_room
    - light.kitchen
    - cover.garage_door
```

### Domaines Supportés

Voici les domaines Home Assistant supportés :

- **Éclairage** : `light` (allumer, éteindre, régler la luminosité)
- **Volets** : `cover` (ouvrir, fermer, régler la position)
- **Aspirateur** : `vacuum` (démarrer, arrêter, retourner à la base)
- **Scènes** : `scene` (activer une scène)
- **Interrupteurs** : `switch` (allumer, éteindre)
- **Climatisation** : `climate` (régler la température, mode)
- **Médias** : `media_player` (lecture, pause, volume)
- **Automatisations** : `automation` (démarrer, arrêter)
- **Scripts** : `script` (exécuter un script)

### Configuration des Actions Personnalisées

Vous pouvez créer des actions personnalisées dans Home Assistant :

```yaml
# configuration.yaml
automation:
  - alias: "Action personnalisée - Bonjour"
    trigger:
      - platform: event
        event_type: jarvis_custom_action
        event_data:
          action: say_hello
    action:
      - service: notify.mobile_app
        data:
          message: "Bonjour ! Comment puis-je vous aider ?"
```

---

## 🤖 Configuration de l'Autonomie

L'autonomie permet à Jarvis de prendre des décisions et d'exécuter des actions sans votre intervention.

### Paramètres

| Paramètre | Type | Description | Valeur par défaut | Requis |
|-----------|------|-------------|-------------------|--------|
| `autonomy_enabled` | boolean | Activer l'autonomie | `false` | ❌ Non |
| `autonomy_interval` | integer | Intervalle de vérification (secondes) | `30` | ❌ Non |
| `autonomy_rules` | list | Règles d'autonomie à activer | `[]` | ❌ Non |
| `auto_rules` | list | Règles automatiques (format texte) | `[]` | ❌ Non |
| `approvers` | list | Entités qui peuvent approuver les actions | `[]` | ❌ Non |
| `proposal_ttl_minutes` | integer | TTL des propositions (minutes) | `120` | ❌ Non |
| `daily_report_time` | string | Heure du rapport quotidien | `""` | ❌ Non |

### Exemple de Configuration

```yaml
options:
  autonomy_enabled: true
  autonomy_interval: 15
  autonomy_rules:
    - "allumer_lumieres_soir"
    - "eteindre_lumieres_nuit"
    - "fermer_volets_coucher"
  auto_rules:
    - "if sun.sun below_horizon and binary_sensor.presence_living_room on then light.turn_on light.living_room"
    - "if time after 23:00 then light.turn_off all"
  approvers:
    - "person.olivier"
    - "person.marie"
  proposal_ttl_minutes: 60
  daily_report_time: "20:00"
```

### Règles d'Autonomie

Les règles d'autonomie sont définies dans le fichier `app/autonomy/rules.py`. Voici quelques exemples :

#### Règle : Allumer les lumières le soir

```python
Rule(
    name="allumer_lumieres_soir",
    description="Allumer les lumières du salon quand il fait nuit et qu'il y a quelqu'un",
    conditions=[
        Condition(entity="sun.sun", state="below_horizon"),
        Condition(entity="binary_sensor.presence_living_room", state="on")
    ],
    actions=[
        Action(domain="light", service="turn_on", entity_id="light.living_room")
    ]
)
```

#### Règle : Éteindre les lumières la nuit

```python
Rule(
    name="eteindre_lumieres_nuit",
    description="Éteindre toutes les lumières à 23h",
    conditions=[
        Condition(time="after 23:00")
    ],
    actions=[
        Action(domain="light", service="turn_off", entity_id="all")
    ]
)
```

### Règles Automatiques (Format Texte)

Vous pouvez définir des règles simples directement dans `config.yaml` :

```yaml
auto_rules:
  # Format : if [condition] then [action]
  - "if sun.sun below_horizon and binary_sensor.presence_living_room on then light.turn_on light.living_room"
  - "if time after 23:00 then light.turn_off all"
  - "if temperature sensor.living_room_temperature > 25 then climate.set_temperature climate.living_room 22"
```

### Conditions Supportées

| Type | Format | Exemple |
|------|--------|---------|
| État d'une entité | `entity state` | `sun.sun below_horizon` |
| Heure | `time after/hour` | `time after 23:00` |
| Température | `entity > valeur` | `sensor.temperature > 25` |
| Présence | `entity on/off` | `binary_sensor.presence on` |
| ET logique | `condition and condition` | `sun.sun below_horizon and presence on` |
| OU logique | `condition or condition` | `presence_living_room on or presence_kitchen on` |

### Actions Supportées

| Domaine | Service | Paramètres | Exemple |
|---------|---------|------------|---------|
| light | turn_on | entity_id | `light.turn_on light.living_room` |
| light | turn_off | entity_id | `light.turn_off light.living_room` |
| light | toggle | entity_id | `light.toggle light.living_room` |
| cover | open | entity_id | `cover.open_cover cover.garage` |
| cover | close | entity_id | `cover.close_cover cover.garage` |
| climate | set_temperature | entity_id, temperature | `climate.set_temperature climate.living_room 22` |
| vacuum | start | entity_id | `vacuum.start vacuum.robot` |
| scene | activate | entity_id | `scene.activate scene.good_morning` |

---

## 👤 Configuration de la Sécurité

La sécurité est essentielle pour protéger votre système domotique.

### Paramètres

| Paramètre | Type | Description | Valeur par défaut | Requis |
|-----------|------|-------------|-------------------|--------|
| `user_roles` | list | Rôles des utilisateurs | `[]` | ❌ Non |
| `voice_pin` | string | Code PIN pour la voix | `""` | ❌ Non |
| `voice_enabled` | boolean | Activer la voix | `false` | ❌ Non |

### Exemple de Configuration

```yaml
options:
  user_roles:
    - "olivier:admin"
    - "marie:user"
    - "enfant:guest"
  voice_pin: "1234"
  voice_enabled: true
```

### Rôles et Permissions

| Rôle | Permissions |
|------|-------------|
| `admin` | Accès complet à toutes les fonctionnalités |
| `user` | Accès aux commandes de base, mais pas à la configuration |
| `guest` | Accès limité (lecture seulement) |

### Configuration des Rôles

Vous pouvez configurer des permissions personnalisées :

```yaml
options:
  user_roles:
    - "olivier:admin:read,write,execute,configure"
    - "marie:user:read,write,execute"
    - "enfant:guest:read"
```

### Sécurité Vocale

Pour protéger l'accès vocal :

```yaml
options:
  voice_enabled: true
  voice_pin: "1234"
```

Quand la voix est activée avec un code PIN, l'utilisateur devra dire le code PIN avant de pouvoir exécuter des commandes.

---

## 👁️ Configuration de la Vision (Frigate)

La vision permet à Jarvis de détecter et de réagir à des événements visuels.

### Paramètres

| Paramètre | Type | Description | Valeur par défaut | Requis |
|-----------|------|-------------|-------------------|--------|
| `vision_enabled` | boolean | Activer la vision | `false` | ❌ Non |
| `frigate_url` | string | URL de l'instance Frigate | `""` | ✅ Oui (si vision_enabled) |
| `vision_labels` | list | Étiquettes à détecter | `[person]` | ❌ Non |
| `vision_cameras` | list | Caméras à surveiller | `[]` | ❌ Non |
| `vision_api_key` | string | Clé API pour Frigate | `""` | ❌ Non |
| `vision_model` | string | Modèle de vision à utiliser | `""` | ❌ Non |
| `vision_daily_budget` | integer | Budget quotidien en minutes | `60` | ❌ Non |
| `vision_cooldown_minutes` | integer | Temps de refroidissement entre les analyses | `5` | ❌ Non |

### Exemple de Configuration

```yaml
options:
  vision_enabled: true
  frigate_url: "http://192.168.1.100:5000"
  vision_labels:
    - person
    - dog
    - cat
    - car
  vision_cameras:
    - camera.front_door
    - camera.backyard
    - camera.driveway
  vision_api_key: "YOUR_FRIGATE_API_KEY"
  vision_model: "gemini-3.6-flash"
  vision_daily_budget: 120
  vision_cooldown_minutes: 10
```

### Étiquettes Supportées

Les étiquettes supportées dépendent de votre modèle Frigate. Voici les étiquettes courantes :

- `person` : Personne
- `dog` : Chien
- `cat` : Chat
- `car` : Voiture
- `truck` : Camion
- `motorcycle` : Moto
- `bicycle` : Vélo
- `bird` : Oiseau
- `squirrel` : Écureuil

### Configuration de Frigate

Assurez-vous que Frigate est correctement configuré :

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
```

---

## 📊 Configuration du Monitoring

Le monitoring permet de surveiller les performances de votre système.

### Variables d'Environnement

| Variable | Type | Description | Valeur par défaut |
|----------|------|-------------|-------------------|
| `PERFORMANCE_MONITORING_ENABLED` | boolean | Activer le monitoring des performances | `true` |
| `CACHE_ENABLED` | boolean | Activer le cache | `true` |
| `BATCH_PROCESSING_ENABLED` | boolean | Activer le traitement par lots | `true` |

### Configuration dans `config.yaml`

```yaml
# Ces paramètres sont configurés via des variables d'environnement
# ou directement dans le code
```

### Paramètres du Cache

Le cache est configuré automatiquement, mais vous pouvez ajuster les paramètres :

```python
# Dans main.py ou via l'API
cache_manager = CacheManager()
action_cache = await cache_manager.create_lru_cache("actions", max_size=100)
decision_cache = await cache_manager.create_ttl_cache("decisions", default_ttl=300.0)
```

### Paramètres du Pool de Connexions

```python
# Pool de connexions SQLite
connection_pool = DatabaseConnectionPool(
    database_path="/config/jarvis.db",
    max_size=10,
    min_size=2
)

# Pool de connexions HTTP
http_pool = HTTPConnectionPool(
    max_connections=100,
    connector_limit=10,
    timeout=30.0
)
```

### Paramètres du Batch Processor

```python
# Traitement par lots
batch_processor = BatchProcessor(
    processor=your_processor_function,
    batch_size=10,
    max_concurrency=5,
    timeout=30.0,
    retry_delay=1.0
)
```

---

## 🔄 Configuration des Mises à Jour

Les mises à jour permettent à Jarvis de se tenir à jour avec les dernières fonctionnalités.

### Vérification Automatique

La vérification des mises à jour est effectuée automatiquement via l'API GitHub.

### Endpoints API

| Endpoint | Description |
|----------|-------------|
| `GET /api/version` | Obtenir les informations de version |
| `GET /api/version/check` | Vérifier les mises à jour disponibles |
| `GET /api/version/notify` | Obtenir les notifications de mise à jour |

### Exemple de Vérification

```bash
# Vérifier la version actuelle
curl http://localhost:8099/api/version

# Vérifier les mises à jour
curl http://localhost:8099/api/version/check

# Obtenir les notifications
curl http://localhost:8099/api/version/notify
```

### Configuration du Versionnement

Le fichier `version.json` contient les informations de version :

```json
{
  "version": "3.9.0",
  "build_date": "2026-11-11T15:00:00Z",
  "git_commit": "abc123",
  "git_branch": "main",
  "is_dev": false,
  "changelog": [
    "Documentation complète",
    "Revue finale"
  ],
  "features": [
    "Assistant IA complet",
    "Monitoring et Sécurité",
    "Optimisation des performances"
  ]
}
```

---

## 📌 Configuration Avancée

### 1. Configuration des Règles Personnalisées

Vous pouvez créer des règles personnalisées dans Python :

```python
from jarvis_ha_control.app.autonomy.rules import Rule, Condition, Action

# Créer une règle personnalisée
custom_rule = Rule(
    name="ma_regle_personnalisee",
    description="Ma règle personnalisée",
    conditions=[
        Condition(entity="sun.sun", state="below_horizon"),
        Condition(entity="binary_sensor.motion_living_room", state="on")
    ],
    actions=[
        Action(domain="light", service="turn_on", entity_id="light.living_room"),
        Action(domain="notify", service="mobile_app", data={"message": "Mouvement détecté"})
    ],
    priority=10
)

# Ajouter la règle au moteur
autonomy.add_rule(custom_rule)
```

### 2. Configuration des Handlers Personnalisés

Vous pouvez ajouter des handlers personnalisés pour des événements spécifiques :

```python
async def my_custom_handler(event_data):
    """Handler personnalisé pour un événement."""
    logger.info(f"Événement personnalisé reçu: {event_data}")
    # Faire quelque chose avec l'événement
    return {"status": "success"}

# Ajouter le handler
autonomy.add_handler("my_custom_event", my_custom_handler)
```

### 3. Configuration des Middlewares

Vous pouvez ajouter des middlewares pour intercepter les requêtes :

```python
from fastapi import Request

async def my_middleware(request: Request, call_next):
    """Middleware personnalisé."""
    # Avant le traitement
    logger.info(f"Requête reçue: {request.url}")
    
    response = await call_next(request)
    
    # Après le traitement
    logger.info(f"Requête traitée: {request.url}")
    
    return response

# Ajouter le middleware
app.middleware("http")(my_middleware)
```

### 4. Configuration des Plugins

Vous pouvez créer des plugins personnalisés :

```python
class MyCustomPlugin:
    """Plugin personnalisé."""
    
    def __init__(self, autonomy_engine):
        self.autonomy = autonomy_engine
    
    async def on_start(self):
        """Appelé au démarrage."""
        logger.info("Plugin personnalisé démarré")
    
    async def on_stop(self):
        """Appelé à l'arrêt."""
        logger.info("Plugin personnalisé arrêté")
    
    async def on_event(self, event):
        """Appelé lors d'un événement."""
        logger.info(f"Événement: {event}")

# Ajouter le plugin
autonomy.add_plugin(MyCustomPlugin(autonomy))
```

---

## ✅ Validation de la Configuration

### 1. Valider le fichier `config.yaml`

```bash
# Utiliser un validateur YAML
python -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

### 2. Vérifier les paramètres requis

```python
from jarvis_ha_control.app.config import Config

config = Config()
config.validate()
```

### 3. Tester la connexion à l'API Gemini

```python
from jarvis_ha_control.app.assistant.gemini_engine import JarvisEngine

engine = JarvisEngine()
try:
    response = await engine.chat("Bonjour")
    print("Connexion à Gemini : OK")
except Exception as e:
    print(f"Erreur de connexion à Gemini : {e}")
```

### 4. Tester la connexion à Home Assistant

```python
from jarvis_ha_control.app.autonomy.ha import HaClient

client = HaClient("http://localhost:8123", "", "YOUR_TOKEN")
try:
    states = await client.get_states()
    print("Connexion à Home Assistant : OK")
except Exception as e:
    print(f"Erreur de connexion à Home Assistant : {e}")
```

---

## 📚 Ressources Supplémentaires

- [Guide d'Installation](INSTALLATION.md)
- [Guide Utilisateur](USER_GUIDE.md)
- [API Reference](API_REFERENCE.md)
- [Architecture](ARCHITECTURE.md)
- [Documentation Technique](TECHNICAL.md)

---

**Configuration terminée ! 🎉**
