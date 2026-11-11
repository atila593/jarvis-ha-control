# 🏗️ Architecture

Jarvis HA Control suit une **architecture modulaire** avec separation claire des responsabilites.

## 🎯 Vue d'Ensemble

```
┌─────────────────────────────────────────────────────────────┐
│                    JARVIS HA CONTROL                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   FastAPI   │  │  Autonomy   │  │  Agents     │        │
│  │   (API)     │  │   Engine    │  │   Module    │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                 │
│  ┌──────▼────────────────▼────────────────▼─────────────┐  │
│  │                    Performance Module                   │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │  │
│  │  │  Cache  │  │  Pool   │  │ Batch   │  │ Monitor │  │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    Home Assistant Integration            │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                │  │
│  │  │  REST   │  │WebSocket│  │  Store  │                │  │
│  │  └─────────┘  └─────────┘  └─────────┘                │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 📦 Modules Principaux

### 1. **Assistant Module** (`app/assistant/`)
- `gemini_engine.py` : Moteur IA avec Gemini
- `prompts.py` : Prompts systeme

### 2. **Autonomy Module** (`app/autonomy/`)
- `engine.py` : Moteur d'autonomie
- `rules.py` : Gestion des regles
- `confidence.py` : Systeme de confiance
- `ha.py` : Client REST HA
- `ha_websocket.py` : Client WebSocket HA
- `store.py` : Stockage SQLite
- `vision.py` : Integration Frigate
- `engineer.py` : Modification entites
- `access.py` : Gestion des acces

### 3. **Agents Module** (`app/agents/`)
- `orchestrator.py` : Coordination des agents
- `conversation_agent.py` : Conversation
- `decision_agent.py` : Prise de decision
- `action_agent.py` : Execution actions
- `monitoring_agent.py` : Monitoring systeme
- `security_agent.py` : Securite

### 4. **Performance Module** (`app/performance/`)
- `cache.py` : LRU et TTL Cache
- `connection_pool.py` : Pool de connexions
- `batch_processor.py` : Traitement par lots
- `performance_monitor.py` : Monitoring performances
- `optimizer.py` : Optimisation automatique

### 5. **Tools Module** (`app/tools/`)
- `toolbox.py` : Outils utilitaires
- `actions.py` : Execution actions HA
- `speak.py` : Synthese vocale
- `status.py` : Statut systeme
- `presence.py` : Detection presence
- `sys_diagnose.py` : Diagnostic

## 🔄 Flux de Donnees

### Commande Utilisateur
```
Utilisateur -> API -> Orchestrator -> Conversation -> Decision -> Action -> HA
```

### Autonomie
```
HA Events (WebSocket) -> Autonomy Engine -> Decision -> Action -> HA
```

### Vision (Frigate)
```
Frigate Events -> Vision Module -> Autonomy Engine -> Action -> HA
```

## 🎭 Architecture des Agents

**Orchestrator** coordonne tous les agents :
- Conversation Agent : Comprend la requete
- Decision Agent : Prend une decision
- Action Agent : Execute l'action

## ⚡ Architecture des Performances

- **Cache** : Reduit la latence (LRU, TTL)
- **Connection Pool** : Reutilise les connexions
- **Batch Processor** : Traite plusieurs elements en parallele
- **Performance Monitor** : Surveille les metriques
- **Optimizer** : Ajuste les parametres automatiquement

## 🌐 Integration Home Assistant

- **REST Client** : Appels API HTTP
- **WebSocket Client** : Evenements temps reel
- **Cache Layer** : Optimisation des requetes

## 🔧 Technologies

- **Python** 3.12+
- **FastAPI** : Framework web
- **AppDaemon** : Integration HA
- **Gemini API** : IA
- **SQLite** : Base de donnees
- **psutil** : Monitoring systeme

## 📊 Diagrammes

Voir [TECHNICAL.md](TECHNICAL.md) pour les diagrammes detailles.
