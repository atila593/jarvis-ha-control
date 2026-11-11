# Jarvis HA Control

[![Version](https://img.shields.io/badge/version-3.9.0-blue.svg)](https://github.com/atila593/jarvis-ha-control)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.12+-blue.svg)](https://www.home-assistant.io/)

**Jarvis HA Control** est un assistant IA complet pour Home Assistant avec interface web HUD, diagnostic systeme, reponse vocale Alexa optionnelle, autonomie avancée, monitoring, securite, et optimisation des performances.

---

## 📋 Table des Matières

- [🚀 Fonctionnalités](#-fonctionnalités)
- [📦 Installation](#-installation)
- [⚙️ Configuration](#️-configuration)
- [🎯 Utilisation](#-utilisation)
- [🏗️ Architecture](#-architecture)
- [📊 API Endpoints](#-api-endpoints)
- [🔧 Développement](#-développement)
- [📚 Documentation Technique](#-documentation-technique)
- [🎓 Exemples](#-exemples)
- [🐛 Dépannage](#-dépannage)
- [📜 Licence](#-licence)

---

## 🚀 Fonctionnalités

### ✨ Fonctionnalités Principales

| Version | Fonctionnalité | Description |
|---------|----------------|-------------|
| **3.0.3** | Base | Assistant Gemini avec HUD web et diagnostic |
| **3.1.0** | Webhooks HA | Connexion WebSocket pour réactivité temps réel |
| **3.2.0** | Polling Optimisé | Intervalle adaptatif (5-30s) selon l'activité |
| **3.3.0** | Système de Confiance | Score de confiance dynamique (0.0-1.0) pour les actions autonomes |
| **3.3.1** | FIX Bug Pickle | Correction du bug de sérialisation |
| **3.4.0** | Mémoire & Voix | Mémoire des actions + Validation vocale |
| **3.5.0** | Agents IA | ConversationAgent, DecisionAgent, ActionAgent, Orchestrator |
| **3.6.0** | Monitoring & Sécurité | MonitoringAgent, SecurityAgent, Alertes intelligentes |
| **3.7.0** | Optimisation | Module Performance (Cache, Pool de connexions, Batch processing) |
| **3.8.0** | Intégration | Tests complets + Système de versionnement automatique |
| **3.9.0** | Documentation | Documentation complète + Revue finale |

### 🎯 Capacités

- **🤖 Assistant IA** : Réponses intelligentes avec Gemini (3.6 Flash, 3.5 Flash)
- **🌐 Interface Web** : HUD complet avec visualisation en temps réel
- **🔊 Réponse Vocale** : Intégration avec Alexa et TTS (Piper, etc.)
- **🏠 Contrôle Domotique** : Gestion complète des entités Home Assistant
- **🤖 Autonomie** : Actions automatiques basées sur des règles intelligentes
- **📊 Monitoring** : Surveillance complète du système (CPU, mémoire, disque, réseau)
- **🔒 Sécurité** : Gestion des utilisateurs, rôles, permissions, authentification
- **⚡ Optimisation** : Cache, pool de connexions, batch processing pour maximiser les performances
- **📡 WebSocket** : Connexion temps réel avec Home Assistant
- **🔄 Mises à jour** : Détection automatique des nouvelles versions

---

## 📦 Installation

### Méthode 1 : Via HACS (Recommandé)

1. Ouvrez Home Assistant
2. Allez dans **HACS** > **Intégrations**
3. Cliquez sur **➕ Ajouter une intégration personnalisée**
4. Entrez l'URL du dépôt : `https://github.com/atila593/jarvis-ha-control`
5. Sélectionnez la catégorie **AppDaemon**
6. Installez et redémarrez Home Assistant

### Méthode 2 : Installation Manuelle

1. **Cloner le dépôt** :
   ```bash
   git clone https://github.com/atila593/jarvis-ha-control.git
   cd jarvis-ha-control
   ```

2. **Créer le dossier de configuration** :
   ```bash
   mkdir -p /config/jarvis-ha-control
   cp -r jarvis_ha_control /config/jarvis-ha-control/
   cp config.yaml /config/jarvis-ha-control/
   ```

3. **Configurer dans Home Assistant** :
   - Allez dans **Paramètres** > **AppDaemon**
   - Ajoutez une nouvelle application
   - Sélectionnez le dossier `/config/jarvis-ha-control`
   - Configurez les paramètres dans `config.yaml`

4. **Redémarrer Home Assistant**

### Méthode 3 : Docker (Pour développement)

```bash
# Construire l'image
docker build -t jarvis-ha-control .

# Exécuter le conteneur
docker run -d \
  --name jarvis-ha-control \
  -p 8099:8099 \
  -v /path/to/config:/config \
  -e HA_API_URL=http://homeassistant:8123 \
  -e SUPERVISOR_TOKEN=your_token \
  jarvis-ha-control
```

---

## ⚙️ Configuration

### Fichier `config.yaml`

```yaml
# Configuration de base
name: Jarvis HA Control
version: "3.9.0"
slug: jarvis_ha_control
description: "Assistant Gemini, HUD web et diagnostic systeme pour Home Assistant"

# API Home Assistant
url: https://github.com/atila593/jarvis-ha-control
homeassistant_api: true
hassio_api: true

# Configuration Gemini
options:
  gemini_api_key: "VOTRE_CLE_API_GEMINI"  # Required
  gemini_model: gemini-3.6-flash           # Modèle principal
  gemini_fallback_model: gemini-3.5-flash # Modèle de secours

# Réponse vocale
  speak_service: ""                       # Service de parole (optionnel)
  speak_targets: []                        # Cibles de parole
  auto_speak: false                        # Réponse vocale automatique
  speak_tts_platform: "tts.piper"         # Plateforme TTS
  speak_language: "fr_FR"                 # Langue
  speak_voice: "fr_FR-tom-medium"         # Voix

# Actions
  actions_enabled: true                    # Activer les actions
  allowed_domains:                         # Domaines autorisés
    - light
    - cover
    - vacuum
    - scene
    - switch
  action_entities: []                      # Entités spécifiques autorisées

# Autonomie
  autonomy_enabled: false                  # Activer l'autonomie
  autonomy_interval: 30                    # Intervalle de vérification (secondes)
  autonomy_rules: []                      # Règles d'autonomie
  auto_rules: []                          # Règles automatiques
  approvers: []                            # Approbateurs
  proposal_ttl_minutes: 120               # TTL des propositions (minutes)

# Présence
  presence_prefix: ""                     # Préfixe de présence
  presence_zone_names: []                 # Noms des zones de présence

# Disponibilité
  quiet_start: "23:00"                    # Début de la période calme
  quiet_end: "07:00"                      # Fin de la période calme
  unavailable_minutes: 30                 # Minutes d'indisponibilité

# Ingénieur (modification automatique)
  engineer_enabled: false                  # Activer l'ingénieur
  engineer_edit_existing: false            # Modifier les entités existantes
  stale_days: 7                           # Jours avant qu'une entité soit obsolète

# Vision (Frigate)
  vision_enabled: false                    # Activer la vision
  frigate_url: ""                         # URL de Frigate
  vision_labels:                           # Étiquettes à détecter
    - person
  vision_cameras: []                       # Caméras à surveiller
  vision_api_key: ""                      # Clé API pour la vision
  vision_model: ""                        # Modèle de vision
  vision_daily_budget: 60                  # Budget quotidien (en minutes)
  vision_cooldown_minutes: 5              # Temps de refroidissement

# Mémoire et Voix
  memory_enabled: false                   # Activer la mémoire
  voice_enabled: false                     # Activer la voix
  voice_pin: ""                            # Code PIN pour la voix
  user_roles: []                           # Rôles des utilisateurs

# Rapports
  notify_service: ""                      # Service de notification
  daily_report_time: ""                   # Heure du rapport quotidien
```

### Variables d'Environnement

| Variable | Description | Valeur par défaut |
|----------|-------------|-------------------|
| `JARVIS_DEV` | Mode développement | `false` |
| `JARVIS_VERSION` | Version de l'application | `3.9.0` |
| `HA_WEBSOCKET_ENABLED` | Activer WebSocket | `true` |
| `PERFORMANCE_MONITORING_ENABLED` | Activer le monitoring des performances | `true` |
| `CACHE_ENABLED` | Activer le cache | `true` |
| `BATCH_PROCESSING_ENABLED` | Activer le traitement par lots | `true` |

---

## 🎯 Utilisation

### Commandes de Base

#### 1. Poser une question

```bash
# Via l'API
curl -X POST http://localhost:8099/api/command \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Allume les lumières du salon", "speak": false}'
```

```json
{
  "response": "J'allume les lumières du salon.",
  "actions": [
    {
      "domain": "light",
      "service": "turn_on",
      "entity_id": "light.living_room"
    }
  ]
}
```

#### 2. Obtenir le statut

```bash
curl http://localhost:8099/api/status
```

#### 3. Obtenir un rapport de diagnostic

```bash
curl http://localhost:8099/api/diagnostic
```

#### 4. Vérifier la version

```bash
curl http://localhost:8099/api/version
```

```json
{
  "version": "3.9.0",
  "build_date": "2026-11-11T15:00:00Z",
  "git_commit": "abc123",
  "git_branch": "main",
  "is_dev": false
}
```

#### 5. Vérifier les mises à jour

```bash
curl http://localhost:8099/api/version/check
```

```json
{
  "current_version": "3.9.0",
  "latest_version": "3.9.0",
  "status": "up_to_date",
  "changelog": []
}
```

### Intégration avec Home Assistant

#### 1. Configuration dans `configuration.yaml`

```yaml
# AppDaemon
appdaemon:
  apps:
    jarvis:
      module: jarvis_ha_control
      class: JarvisApp
      ha_url: http://localhost:8123
      token: YOUR_LONG_LIVED_TOKEN
```

#### 2. Utilisation des services

```yaml
# automation.yaml
automation:
  - alias: "Demander à Jarvis"
    trigger:
      - platform: state
        entity_id: input_text.jarvis_command
    action:
      - service: appdaemon.jarvis_ha_control
        data:
          command: "{{ trigger.to_state.state }}"
```

### Interface Web

L'interface web est disponible à l'adresse : `http://[IP_HOME_ASSISTANT]:8099`

Fonctionnalités de l'interface :
- **Tableau de bord** : Vue d'ensemble du système
- **Historique** : Historique des commandes et actions
- **Monitoring** : Métriques de performance en temps réel
- **Configuration** : Gestion des paramètres
- **Mises à jour** : Vérification des mises à jour disponibles

---

## 🏗️ Architecture

### Diagramme Global

```
┌─────────────────────────────────────────────────────────────────────┐
│                         JARVIS HA CONTROL                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │   FastAPI       │    │   Autonomy      │    │   Performance   │  │
│  │   (API REST)    │    │   Engine        │    │   Module        │  │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘  │
│           │                      │                      │            │
│  ┌────────▼────────┐    ┌────────▼────────┐    ┌────────▼────────┐  │
│  │  Command Handler │    │  Agents IA      │    │  Cache Manager  │  │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘  │
│           │                      │                      │            │
│  ┌────────▼────────┐    ┌────────▼────────┐    ┌────────▼────────┐  │
│  │   WebSocket     │    │  Conversation   │    │  Connection     │  │
│  │   Client        │    │  Agent          │    │  Pool           │  │
│  └─────────────────┘    └────────┬────────┘    └─────────────────┘  │
│                                          │                         │
│  ┌─────────────────┐    ┌────────▼────────┐                      │
│  │   HA Client     │    │  Decision       │                      │
│  │   (API HA)      │    │  Agent          │                      │
│  └─────────────────┘    └────────┬────────┘                      │
│                                          │                         │
│                                  ┌───────▼───────┐                │
│                                  │  Action        │                │
│                                  │  Agent         │                │
│                                  └───────┬───────┘                │
│                                          │                         │
│                                  ┌───────▼───────┐                │
│                                  │  Orchestrator │                │
│                                  └───────────────┘                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Modules Principaux

#### 1. **Assistant Module** (`app/assistant/`)
- `gemini_engine.py` : Moteur de traitement des requêtes avec Gemini
- `prompts.py` : Prompts système pour l'IA

#### 2. **Autonomy Module** (`app/autonomy/`)
- `engine.py` : Moteur d'autonomie principal
- `rules.py` : Gestion des règles d'autonomie
- `confidence.py` : Système de confiance dynamique
- `ha.py` : Client Home Assistant
- `ha_websocket.py` : Client WebSocket pour Home Assistant
- `store.py` : Stockage des données
- `vision.py` : Intégration avec Frigate pour la vision
- `engineer.py` : Modification automatique des entités
- `access.py` : Gestion des accès et permissions

#### 3. **Agents Module** (`app/agents/`)
- `orchestrator.py` : Orchestrateur principal
- `conversation_agent.py` : Agent de conversation
- `decision_agent.py` : Agent de décision
- `action_agent.py` : Agent d'action
- `monitoring_agent.py` : Agent de monitoring
- `security_agent.py` : Agent de sécurité

#### 4. **Performance Module** (`app/performance/`)
- `cache.py` : Gestion du cache (LRU, TTL)
- `connection_pool.py` : Pool de connexions (SQLite, HTTP)
- `batch_processor.py` : Traitement par lots
- `performance_monitor.py` : Monitoring des performances
- `optimizer.py` : Optimisation automatique

#### 5. **Tools Module** (`app/tools/`)
- `toolbox.py` : Boîte à outils principale
- `actions.py` : Exécution des actions
- `speak.py` : Synthèse vocale
- `status.py` : Statut du système
- `presence.py` : Détection de présence
- `sys_diagnose.py` : Diagnostic système

#### 6. **Version Module** (`app/version.py`)
- Gestion des versions
- Détection des mises à jour
- Notifications

### Flux de Traitement

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Requête   │────▶│ Conversation │────▶│   Décision  │
│   Utilisateur│     │    Agent     │     │    Agent     │
└─────────────┘     └─────────────┘     └─────────────┘
                                                      │
                                                      ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Validation │◀────│   Action    │◀────│ Orchestrator│
│  Sécurité   │     │    Agent     │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
      │
      ▼
┌─────────────┐
│   Exécution  │
│   Action     │
└─────────────┘
```

---

## 📊 API Endpoints

### Endpoints Principaux

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/status` | Statut du système |
| GET | `/api/presence` | Statut de présence |
| POST | `/api/command` | Exécuter une commande |
| POST | `/api/speak` | Synthèse vocale |
| GET | `/api/diagnostic` | Diagnostic système |
| GET | `/api/report` | Rapport d'activité |
| GET | `/api/diagnostics` | Diagnostics complets |
| GET | `/api/autonomy` | Statut de l'autonomie |
| GET | `/api/proposals` | Liste des propositions |
| POST | `/api/proposals/{pid}/approve` | Approuver une proposition |
| POST | `/api/proposals/{pid}/reject` | Rejeter une proposition |
| GET | `/api/journal` | Journal des actions |
| POST | `/api/voice/ask` | Question vocale |
| GET | `/api/changes` | Liste des changements |
| POST | `/api/changes/{cid}/undo` | Annuler un changement |
| GET | `/api/hygiene` | Statut d'hygiène |
| GET | `/api/memory` | Mémoire des faits |
| DELETE | `/api/memory/{fid}` | Supprimer un fait |

### Endpoints de Version (Nouveau 3.8.0+)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/version` | Obtenir les informations de version |
| GET | `/api/version/check` | Vérifier les mises à jour disponibles |
| GET | `/api/version/notify` | Obtenir les notifications de mise à jour |

### Exemples de Réponses

#### `/api/status`

```json
{
  "version": "3.9.0",
  "status": "running",
  "autonomy_enabled": true,
  "autonomy_status": "active",
  "websocket_connected": true,
  "last_command": "2026-11-11T15:00:00Z",
  "commands_today": 42,
  "actions_today": 25
}
```

#### `/api/version`

```json
{
  "version": "3.9.0",
  "build_date": "2026-11-11T15:00:00Z",
  "git_commit": "abc123def456",
  "git_branch": "main",
  "is_dev": false,
  "changelog": [
    "Documentation complète",
    "Revue finale",
    "Optimisation des performances"
  ],
  "features": [
    "Assistant IA complet",
    "Monitoring et Sécurité",
    "Optimisation des performances",
    "Tests d'intégration complets"
  ]
}
```

#### `/api/version/check`

```json
{
  "current_version": "3.9.0",
  "latest_version": "3.9.0",
  "status": "up_to_date",
  "changelog": [],
  "download_url": null,
  "release_date": "2026-11-11T15:00:00Z",
  "is_major": false,
  "is_minor": false,
  "is_patch": false
}
```

#### `/api/version/check` (Mise à jour disponible)

```json
{
  "current_version": "3.8.0",
  "latest_version": "3.9.0",
  "status": "update_available",
  "changelog": [
    "Documentation complète",
    "Revue finale"
  ],
  "download_url": "https://github.com/atila593/jarvis-ha-control/releases/download/v3.9.0/jarvis-ha-control.zip",
  "release_date": "2026-11-11T15:00:00Z",
  "is_major": false,
  "is_minor": true,
  "is_patch": false
}
```

---

## 🔧 Développement

### Prérequis

- Python 3.12+
- Poetry (pour la gestion des dépendances)
- Git
- Home Assistant 2024.12+

### Installation pour Développement

1. **Cloner le dépôt** :
   ```bash
   git clone https://github.com/atila593/jarvis-ha-control.git
   cd jarvis-ha-control
   ```

2. **Installer les dépendances** :
   ```bash
   poetry install
   ```

3. **Configurer l'environnement** :
   ```bash
   cp .env.example .env
   # Éditer .env avec vos paramètres
   ```

4. **Exécuter en mode développement** :
   ```bash
   export JARVIS_DEV=true
   python -m jarvis_ha_control.app.main
   ```

### Structure du Projet

```
jarvis-ha-control/
├── jarvis_ha_control/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # Point d'entrée principal
│   │   ├── config.py            # Configuration
│   │   ├── assistant/
│   │   │   ├── __init__.py
│   │   │   ├── gemini_engine.py # Moteur Gemini
│   │   │   └── prompts.py       # Prompts système
│   │   ├── autonomy/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py        # Moteur d'autonomie
│   │   │   ├── rules.py         # Règles d'autonomie
│   │   │   ├── confidence.py    # Système de confiance
│   │   │   ├── ha.py            # Client HA
│   │   │   ├── ha_websocket.py  # Client WebSocket
│   │   │   ├── store.py         # Stockage
│   │   │   ├── vision.py        # Vision (Frigate)
│   │   │   ├── engineer.py      # Ingénieur
│   │   │   └── access.py        # Accès
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator.py  # Orchestrateur
│   │   │   ├── conversation_agent.py
│   │   │   ├── decision_agent.py
│   │   │   ├── action_agent.py
│   │   │   ├── monitoring_agent.py
│   │   │   └── security_agent.py
│   │   ├── performance/
│   │   │   ├── __init__.py
│   │   │   ├── cache.py         # Cache
│   │   │   ├── connection_pool.py
│   │   │   ├── batch_processor.py
│   │   │   ├── performance_monitor.py
│   │   │   └── optimizer.py     # Optimiseur
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── toolbox.py
│   │   │   ├── actions.py
│   │   │   ├── speak.py
│   │   │   ├── status.py
│   │   │   ├── presence.py
│   │   │   └── sys_diagnose.py
│   │   └── version.py           # Gestion des versions
│   ├── version.json             # Informations de version
│   └── config.yaml              # Configuration
├── tests/
│   ├── __init__.py
│   ├── test_agents.py          # Tests des agents
│   ├── test_performance.py      # Tests des performances
│   ├── test_integration.py      # Tests d'intégration
│   └── test_version.py          # Tests de version
├── docs/
│   └── (documentation)
├── .github/
│   └── workflows/
│       └── (CI/CD)
├── README.md
├── CHANGELOG.md
├── LICENSE
└── poetry.lock
```

### Exécution des Tests

```bash
# Tous les tests
pytest tests/

# Tests spécifiques
pytest tests/test_agents.py
pytest tests/test_performance.py
pytest tests/test_integration.py
pytest tests/test_version.py

# Avec couverture
pytest tests/ --cov=jarvis_ha_control --cov-report=html
```

### Linting et Formatage

```bash
# Linting
ruff check jarvis_ha_control/

# Formatage
ruff format jarvis_ha_control/

# Typage
mypy jarvis_ha_control/
```

---

## 📚 Documentation Technique

### Modules en Détail

#### 1. Assistant Module

Le module assistant gère les interactions avec l'IA Gemini.

**Fichiers** :
- `gemini_engine.py` : Moteur principal avec gestion des erreurs et retry
- `prompts.py` : Prompts système personnalisables

**Fonctionnalités** :
- Traitement des requêtes en langage naturel
- Gestion des erreurs API (429, 500, etc.)
- Retry exponentiel avec jitter
- Fallback automatique vers le modèle de secours

#### 2. Autonomy Module

Le module d'autonomie permet à Jarvis de prendre des décisions et d'exécuter des actions de manière autonome.

**Fichiers** :
- `engine.py` : Moteur principal avec boucle d'exécution
- `rules.py` : Gestion des règles d'autonomie
- `confidence.py` : Système de confiance dynamique (0.0-1.0)
- `ha.py` : Client Home Assistant avec cache
- `ha_websocket.py` : Client WebSocket pour les événements temps réel
- `store.py` : Stockage SQLite des faits et actions
- `vision.py` : Intégration avec Frigate pour la détection visuelle
- `engineer.py` : Modification automatique des entités
- `access.py` : Gestion des rôles et permissions

**Fonctionnalités** :
- Exécution autonome basée sur des règles
- Score de confiance dynamique
- Détection des événements en temps réel
- Stockage persistant des actions
- Détection visuelle avec Frigate
- Gestion des rôles utilisateurs

#### 3. Agents Module

Les agents sont des composants spécialisés qui travaillent ensemble pour fournir des fonctionnalités avancées.

**Agents** :
- **Orchestrator** : Coordonne tous les agents
- **ConversationAgent** : Gère les conversations avec l'utilisateur
- **DecisionAgent** : Prend des décisions basées sur le contexte
- **ActionAgent** : Exécute les actions sur Home Assistant
- **MonitoringAgent** : Surveille le système (CPU, mémoire, disque, réseau)
- **SecurityAgent** : Gère la sécurité (utilisateurs, rôles, permissions)

**Fonctionnalités** :
- Workflow : Conversation → Décision → Action
- Validation des préconditions et postconditions
- Rollback automatique en cas d'échec
- Journalisation complète des actions

#### 4. Performance Module

Le module de performance optimise les performances de l'application.

**Fichiers** :
- `cache.py` : Cache LRU et TTL
- `connection_pool.py` : Pool de connexions SQLite et HTTP
- `batch_processor.py` : Traitement par lots
- `performance_monitor.py` : Monitoring des performances
- `optimizer.py` : Optimisation automatique

**Fonctionnalités** :
- Réduction de la latence avec le cache
- Réutilisation des connexions
- Traitement parallèle des actions
- Surveillance des métriques système
- Optimisation automatique des paramètres

#### 5. Tools Module

Le module tools fournit des utilitaires pour diverses fonctionnalités.

**Fichiers** :
- `toolbox.py` : Boîte à outils principale
- `actions.py` : Exécution des actions Home Assistant
- `speak.py` : Synthèse vocale
- `status.py` : Statut du système
- `presence.py` : Détection de présence
- `sys_diagnose.py` : Diagnostic système

---

## 🎓 Exemples

### Exemple 1 : Créer une règle d'autonomie

```python
from jarvis_ha_control.app.autonomy.rules import Rule, Condition, Action

# Créer une règle simple
rule = Rule(
    name="allumer_lumieres_salon_soir",
    description="Allumer les lumières du salon le soir",
    conditions=[
        Condition(
            entity="sun.sun",
            state="below_horizon"
        ),
        Condition(
            entity="binary_sensor.presence_living_room",
            state="on"
        )
    ],
    actions=[
        Action(
            domain="light",
            service="turn_on",
            entity_id="light.living_room"
        )
    ]
)

# Ajouter la règle au moteur d'autonomie
autonomy.add_rule(rule)
```

### Exemple 2 : Utiliser le cache

```python
from jarvis_ha_control.app.performance.cache import LRUCache

# Créer un cache
cache = LRUCache(max_size=100)

# Stocker une valeur
await cache.set("user_preferences", {"theme": "dark", "language": "fr"})

# Récupérer une valeur
preferences = await cache.get("user_preferences")
print(preferences)  # {"theme": "dark", "language": "fr"}
```

### Exemple 3 : Traitement par lots

```python
from jarvis_ha_control.app.performance.batch_processor import BatchProcessor

# Créer un processeur par lots
async def process_light(entity_id):
    # Exécuter une action sur l'entité
    return f"processed_{entity_id}"

batch_processor = BatchProcessor(
    processor=process_light,
    batch_size=5,
    max_concurrency=3
)

# Ajouter des éléments
for i in range(20):
    await batch_processor.add_item(f"light.living_room_{i}")

# Attendre la fin du traitement
await batch_processor.wait_for_completion()
```

### Exemple 4 : Monitoring des performances

```python
from jarvis_ha_control.app.performance.performance_monitor import PerformanceMonitor

# Créer un moniteur
monitor = PerformanceMonitor()

# Démarrer la collecte
await monitor.start()

# Attendre quelques secondes
import asyncio
await asyncio.sleep(5)

# Prendre un snapshot
snapshot = await monitor.take_snapshot()
print(snapshot.metrics)

# Arrêter le moniteur
await monitor.stop()
```

### Exemple 5 : Vérifier les mises à jour

```python
from jarvis_ha_control.app.version import check_for_updates

# Vérifier les mises à jour
update_info = await check_for_updates()

if update_info.status.value == "update_available":
    print(f"Nouvelle version {update_info.latest_version} disponible!")
    print("Changements:")
    for change in update_info.changelog:
        print(f"- {change}")
else:
    print("L'application est à jour.")
```

---

## 🐛 Dépannage

### Problèmes Courants

#### 1. Erreur de connexion à l'API Gemini

**Symptômes** :
```
GeminiUnavailable: Failed to connect to Gemini API
```

**Solutions** :
- Vérifiez que votre clé API est correcte
- Vérifiez que vous avez du crédit sur votre compte Google Cloud
- Essayez avec le modèle de secours

#### 2. Erreur de connexion WebSocket

**Symptômes** :
```
WebSocket connection failed
```

**Solutions** :
- Vérifiez que Home Assistant est en cours d'exécution
- Vérifiez que l'URL WebSocket est correcte
- Vérifiez que le token est valide
- Essayez de désactiver WebSocket et utilisez le mode polling

#### 3. Erreur de sérialisation (Pickle)

**Symptômes** :
```
Cannot pickle '_thread.lock' object
```

**Solutions** :
- Cette erreur a été corrigée dans la version 3.3.1
- Mettez à jour vers la dernière version
- Si le problème persiste, utilisez SQLite au lieu du stockage en mémoire

#### 4. Problèmes de performance

**Symptômes** :
- Latence élevée
- Utilisation CPU/mémoire élevée

**Solutions** :
- Activez le monitoring des performances
- Vérifiez les métriques avec `/api/diagnostics`
- Ajustez les paramètres de cache et de batch processing
- Réduisez le nombre de règles d'autonomie actives

#### 5. Mises à jour non détectées

**Symptômes** :
- `/api/version/check` retourne toujours "up_to_date"

**Solutions** :
- Vérifiez votre connexion Internet
- Vérifiez que l'API GitHub est accessible
- Essayez de forcer le rafraîchissement du cache

### Logs et Diagnostic

#### 1. Voir les logs

```bash
# Logs de l'application
tail -f /config/jarvis-ha-control/jarvis.log

# Logs de Home Assistant
journalctl -u hassos-supervisor -f
```

#### 2. Diagnostic système

```bash
curl http://localhost:8099/api/diagnostic
```

#### 3. Vérifier le statut

```bash
curl http://localhost:8099/api/status
```

---

## 📜 Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

## 🙏 Remerciements

- [Home Assistant](https://www.home-assistant.io/) - La meilleure plateforme de domotique
- [Google Gemini](https://ai.google.dev/) - Pour les capacités IA avancées
- [FastAPI](https://fastapi.tiangolo.com/) - Pour le framework web
- [AppDaemon](https://appdaemon.readthedocs.io/) - Pour l'intégration avec Home Assistant

---

## 📞 Support

- **GitHub Issues** : [https://github.com/atila593/jarvis-ha-control/issues](https://github.com/atila593/jarvis-ha-control/issues)
- **Discussions** : [https://github.com/atila593/jarvis-ha-control/discussions](https://github.com/atila593/jarvis-ha-control/discussions)
- **Email** : boucaolivier@gmail.com

---

**Made with ❤️ for Home Assistant**

*© 2026 Jarvis HA Control - Version 3.9.0*