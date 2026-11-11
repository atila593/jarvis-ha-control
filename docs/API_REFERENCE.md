# 📡 API Reference

Cette documentation décrit toutes les endpoints API disponibles dans Jarvis HA Control.

---

## 📋 Table des Matières

- [📌 Informations Générales](#-informations-générales)
- [🔐 Authentification](#-authentification)
- [📊 Endpoints Principaux](#-endpoints-principaux)
- [🤖 Endpoints d'Autonomie](#-endpoints-dautonomie)
- [👁️ Endpoints de Vision](#-endpoints-de-vision)
- [📈 Endpoints de Monitoring](#-endpoints-de-monitoring)
- [🔄 Endpoints de Version](#-endpoints-de-version)
- [🎵 Endpoints Vocaux](#-endpoints-vocaux)
- [💾 Endpoints de Mémoire](#-endpoints-de-mémoire)
- [📝 Endpoints de Configuration](#-endpoints-de-configuration)
- [⚡ Endpoints de Performance](#-endpoints-de-performance)
- [📋 Schémas de Données](#-schémas-de-données)
- [🐛 Codes d'Erreur](#-codes-derreur)
- [📌 Bonnes Pratiques](#-bonnes-pratiques)

---

## 📌 Informations Générales

### URL de Base

```
http://[IP_HOME_ASSISTANT]:8099
```

### Format de Réponse

Toutes les réponses sont au format JSON :

```json
{
  "status": "success|error",
  "data": { ... },
  "message": "Message optionnel",
  "error": "Message d'erreur (si status=error)"
}
```

### En-têtes HTTP

| En-tête | Description | Valeur |
|---------|-------------|--------|
| `Content-Type` | Type de contenu | `application/json` |
| `Authorization` | Authentification | `Bearer [TOKEN]` |
| `Accept` | Types acceptés | `application/json` |

---

## 🔐 Authentification

### Méthodes d'Authentification

Jarvis HA Control supporte plusieurs méthodes d'authentification :

#### 1. Authentification via Home Assistant

Par défaut, Jarvis utilise l'authentification de Home Assistant. Les requêtes doivent provenir de l'IP du proxy Ingress (`172.30.32.2`).

#### 2. Authentification via Token

Vous pouvez configurer un token d'API personnalisé :

```yaml
# config.yaml
options:
  api_token: "VOTRE_TOKEN_SECRET"
```

Puis, incluez le token dans les en-têtes :

```
Authorization: Bearer VOTRE_TOKEN_SECRET
```

#### 3. Authentification de Base

Pour les environnements de développement, vous pouvez désactiver l'authentification :

```yaml
# config.yaml
options:
  auth_enabled: false
```

⚠️ **Attention** : Ne désactivez pas l'authentification en production !

---

## 📊 Endpoints Principaux

### `GET /api/status`

Obtient le statut actuel du système.

**Requête** :
```bash
curl http://localhost:8099/api/status
```

**Réponse** :
```json
{
  "version": "3.9.0",
  "status": "running",
  "autonomy_enabled": true,
  "autonomy_status": "active",
  "websocket_connected": true,
  "last_command": "2026-11-11T15:00:00Z",
  "commands_today": 42,
  "actions_today": 25,
  "uptime": "2h 30m",
  "memory_usage": 62.8,
  "cpu_usage": 45.2
}
```

---

### `POST /api/command`

Exécute une commande.

**Requête** :
```bash
curl -X POST http://localhost:8099/api/command \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Allume la lumière du salon",
    "speak": false,
    "who": "olivier"
  }'
```

**Paramètres** :

| Paramètre | Type | Description | Requis | Valeur par défaut |
|-----------|------|-------------|--------|-------------------|
| `prompt` | string | La commande à exécuter | ✅ Oui | - |
| `speak` | boolean | Si vrai, répondre vocalement | ❌ Non | `false` |
| `who` | string | Identifiant de l'utilisateur | ❌ Non | `""` |

**Réponse** :
```json
{
  "response": "J'allume la lumière du salon.",
  "actions": [
    {
      "domain": "light",
      "service": "turn_on",
      "entity_id": "light.living_room",
      "status": "completed",
      "timestamp": "2026-11-11T15:00:00Z"
    }
  ],
  "confidence": 0.95,
  "processing_time": 150
}
```

---

### `POST /api/speak`

Effectue une synthèse vocale.

**Requête** :
```bash
curl -X POST http://localhost:8099/api/speak \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Bonjour, comment puis-je vous aider ?",
    "target": "phone_olivier"
  }'
```

**Paramètres** :

| Paramètre | Type | Description | Requis | Valeur par défaut |
|-----------|------|-------------|--------|-------------------|
| `text` | string | Le texte à dire | ✅ Oui | - |
| `target` | string | La cible de la parole | ❌ Non | `""` |

**Réponse** :
```json
{
  "status": "success",
  "message": "Message vocal envoyé"
}
```

---

### `GET /api/presence`

Obtient le statut de présence.

**Requête** :
```bash
curl http://localhost:8099/api/presence
```

**Réponse** :
```json
{
  "users": [
    {
      "user_id": "olivier",
      "name": "Olivier",
      "status": "home",
      "last_seen": "2026-11-11T15:00:00Z",
      "zone": "living_room"
    },
    {
      "user_id": "marie",
      "name": "Marie",
      "status": "away",
      "last_seen": "2026-11-11T14:00:00Z",
      "zone": null
    }
  ],
  "zones": [
    {
      "zone_id": "living_room",
      "name": "Salon",
      "users": ["olivier"]
    }
  ]
}
```

---

## 🤖 Endpoints d'Autonomie

### `GET /api/autonomy`

Obtient le statut de l'autonomie.

**Requête** :
```bash
curl http://localhost:8099/api/autonomy
```

**Réponse** :
```json
{
  "enabled": true,
  "status": "active",
  "interval": 30,
  "rules_count": 5,
  "active_rules": [
    {
      "name": "allumer_lumieres_soir",
      "description": "Allumer les lumières le soir",
      "status": "active",
      "last_triggered": "2026-11-11T18:00:00Z",
      "trigger_count": 12
    }
  ],
  "actions_today": 8,
  "proposals_pending": 2
}
```

---

### `GET /api/proposals`

Liste toutes les propositions en attente d'approbation.

**Requête** :
```bash
curl http://localhost:8099/api/proposals
```

**Réponse** :
```json
{
  "proposals": [
    {
      "id": "prop_abc123",
      "rule_name": "allumer_lumieres_soir",
      "description": "Allumer les lumières du salon",
      "actions": [
        {
          "domain": "light",
          "service": "turn_on",
          "entity_id": "light.living_room"
        }
      ],
      "created_at": "2026-11-11T18:00:00Z",
      "expires_at": "2026-11-11T18:30:00Z",
      "status": "pending"
    }
  ],
  "total": 1
}
```

---

### `POST /api/proposals/{pid}/approve`

Approuve une proposition.

**Requête** :
```bash
curl -X POST http://localhost:8099/api/proposals/prop_abc123/approve
```

**Réponse** :
```json
{
  "status": "success",
  "message": "Proposition approuvée",
  "proposal_id": "prop_abc123",
  "actions_executed": [
    {
      "domain": "light",
      "service": "turn_on",
      "entity_id": "light.living_room",
      "status": "completed"
    }
  ]
}
```

---

### `POST /api/proposals/{pid}/reject`

Rejette une proposition.

**Requête** :
```bash
curl -X POST http://localhost:8099/api/proposals/prop_abc123/reject
```

**Réponse** :
```json
{
  "status": "success",
  "message": "Proposition rejetée",
  "proposal_id": "prop_abc123"
}
```

---

## 👁️ Endpoints de Vision

### `GET /api/vision/cameras`

Liste toutes les caméras configurées.

**Requête** :
```bash
curl http://localhost:8099/api/vision/cameras
```

**Réponse** :
```json
{
  "cameras": [
    {
      "id": "camera.front_door",
      "name": "Porte d'entrée",
      "url": "http://192.168.1.100:5000/api/camera/front_door/fs.mp4",
      "status": "active",
      "labels": ["person", "car"],
      "detections_today": 15
    }
  ],
  "total": 1
}
```

---

### `GET /api/vision/detections`

Liste toutes les détections.

**Requête** :
```bash
curl http://localhost:8099/api/vision/detections?camera=front_door&label=person&limit=10
```

**Paramètres de requête** :

| Paramètre | Type | Description | Valeur par défaut |
|-----------|------|-------------|-------------------|
| `camera` | string | Filtrer par caméra | `null` (toutes) |
| `label` | string | Filtrer par étiquette | `null` (toutes) |
| `limit` | integer | Limite le nombre de résultats | `100` |
| `offset` | integer | Décalage pour la pagination | `0` |

**Réponse** :
```json
{
  "detections": [
    {
      "id": "det_abc123",
      "camera_id": "camera.front_door",
      "label": "person",
      "confidence": 0.95,
      "timestamp": "2026-11-11T18:00:00Z",
      "image_url": "http://192.168.1.100:5000/api/events/det_abc123/snapshot.jpg",
      "video_url": "http://192.168.1.100:5000/api/events/det_abc123/clip.mp4",
      "actions_triggered": [
        {
          "type": "notification",
          "target": "phone_olivier",
          "message": "Personne détectée devant la porte"
        }
      ]
    }
  ],
  "total": 15,
  "limit": 10,
  "offset": 0
}
```

---

### `GET /api/vision/detections/{did}`

Obtient les détails d'une détection spécifique.

**Requête** :
```bash
curl http://localhost:8099/api/vision/detections/det_abc123
```

**Réponse** :
```json
{
  "id": "det_abc123",
  "camera_id": "camera.front_door",
  "label": "person",
  "confidence": 0.95,
  "timestamp": "2026-11-11T18:00:00Z",
  "duration": 5.2,
  "bounding_box": {
    "x": 0.45,
    "y": 0.35,
    "width": 0.2,
    "height": 0.4
  },
  "image_url": "http://192.168.1.100:5000/api/events/det_abc123/snapshot.jpg",
  "video_url": "http://192.168.1.100:5000/api/events/det_abc123/clip.mp4",
  "actions_triggered": [
    {
      "type": "notification",
      "target": "phone_olivier",
      "message": "Personne détectée devant la porte",
      "timestamp": "2026-11-11T18:00:01Z"
    }
  ]
}
```

---

## 📈 Endpoints de Monitoring

### `GET /api/diagnostic`

Obtient un diagnostic complet du système.

**Requête** :
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
      "sent": 1024000,
      "received": 2048000
    },
    "temperature": 45.0,
    "uptime": "2h 30m"
  },
  "jarvis": {
    "version": "3.9.0",
    "status": "running",
    "uptime": "2h 30m",
    "commands_today": 42,
    "actions_today": 25,
    "response_time_avg": 150,
    "response_time_max": 500,
    "error_rate": 0.0,
    "cache": {
      "hit_rate": 0.85,
      "size": 42,
      "max_size": 100
    }
  },
  "autonomy": {
    "enabled": true,
    "status": "active",
    "rules_count": 5,
    "actions_today": 8,
    "proposals_pending": 2
  },
  "performance": {
    "cache_hit_rate": 0.85,
    "batch_processing": {
      "items_processed": 100,
      "batches_completed": 10,
      "avg_batch_size": 10
    },
    "connection_pool": {
      "total_connections": 5,
      "available_connections": 3,
      "in_use_connections": 2
    }
  }
}
```

---

### `GET /api/diagnostics`

Obtient des diagnostics détaillés.

**Requête** :
```bash
curl http://localhost:8099/api/diagnostics
```

**Réponse** :
```json
{
  "diagnostics": [
    {
      "name": "gemini_api",
      "status": "healthy",
      "last_check": "2026-11-11T15:00:00Z",
      "response_time": 150,
      "error_count": 0
    },
    {
      "name": "home_assistant_api",
      "status": "healthy",
      "last_check": "2026-11-11T15:00:00Z",
      "response_time": 50,
      "error_count": 0
    },
    {
      "name": "websocket",
      "status": "healthy",
      "last_check": "2026-11-11T15:00:00Z",
      "connected": true,
      "reconnect_count": 0
    },
    {
      "name": "database",
      "status": "healthy",
      "last_check": "2026-11-11T15:00:00Z",
      "size": 1024,
      "tables": 5
    }
  ],
  "last_diagnostic": "2026-11-11T15:00:00Z"
}
```

---

### `GET /api/report`

Obtient un rapport d'activité.

**Requête** :
```bash
curl http://localhost:8099/api/report?days=7
```

**Paramètres de requête** :

| Paramètre | Type | Description | Valeur par défaut |
|-----------|------|-------------|-------------------|
| `days` | integer | Nombre de jours | `1` |

**Réponse** :
```json
{
  "period": {
    "start": "2026-11-04T00:00:00Z",
    "end": "2026-11-11T00:00:00Z",
    "days": 7
  },
  "summary": {
    "commands": 294,
    "actions": 176,
    "errors": 2,
    "avg_response_time": 180,
    "autonomy_actions": 42,
    "detections": 89
  },
  "daily_stats": [
    {
      "date": "2026-11-10",
      "commands": 42,
      "actions": 25,
      "errors": 0,
      "avg_response_time": 150
    },
    {
      "date": "2026-11-09",
      "commands": 50,
      "actions": 30,
      "errors": 1,
      "avg_response_time": 200
    }
  ],
  "top_commands": [
    {
      "command": "allume la lumière",
      "count": 25
    },
    {
      "command": "quelle est la température",
      "count": 20
    }
  ]
}
```

---

## 🔄 Endpoints de Version

### `GET /api/version`

Obtient les informations de version.

**Requête** :
```bash
curl http://localhost:8099/api/version
```

**Réponse** :
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
    "Optimisation des performances",
    "Tests d'intégration complets",
    "Système de versionnement automatique"
  ],
  "features": [
    "Assistant IA complet",
    "Monitoring et Sécurité",
    "Optimisation des performances",
    "Tests d'intégration complets",
    "Mises à jour automatiques"
  ]
}
```

---

### `GET /api/version/check`

Vérifie les mises à jour disponibles.

**Requête** :
```bash
curl http://localhost:8099/api/version/check
```

**Réponse** (à jour) :
```json
{
  "current_version": "3.9.0",
  "latest_version": "3.9.0",
  "status": "up_to_date",
  "changelog": [],
  "download_url": null,
  "release_date": null,
  "is_major": false,
  "is_minor": false,
  "is_patch": false
}
```

**Réponse** (mise à jour disponible) :
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

### `GET /api/version/notify`

Obtient les notifications de mise à jour.

**Requête** :
```bash
curl http://localhost:8099/api/version/notify
```

**Réponse** (à jour) :
```json
{
  "notification": null,
  "status": "up_to_date"
}
```

**Réponse** (mise à jour disponible) :
```json
{
  "notification": "Nouvelle version 3.9.0 disponible (MINEURE)\nChangements:\n- Documentation complète\n- Revue finale",
  "status": "update_available"
}
```

---

## 🎵 Endpoints Vocaux

### `POST /api/voice/ask`

Pose une question vocalement.

**Requête** :
```bash
curl -X POST http://localhost:8099/api/voice/ask \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Allume la lumière du salon",
    "pin": "1234"
  }'
```

**Paramètres** :

| Paramètre | Type | Description | Requis | Valeur par défaut |
|-----------|------|-------------|--------|-------------------|
| `text` | string | Le texte de la commande | ✅ Oui | - |
| `pin` | string | Code PIN pour l'authentification | ❌ Non | `""` |

**Réponse** :
```json
{
  "status": "success",
  "response": "J'allume la lumière du salon.",
  "speak": true,
  "actions": [
    {
      "domain": "light",
      "service": "turn_on",
      "entity_id": "light.living_room"
    }
  ]
}
```

---

## 💾 Endpoints de Mémoire

### `GET /api/memory`

Liste tous les faits en mémoire.

**Requête** :
```bash
curl http://localhost:8099/api/memory
```

**Réponse** :
```json
{
  "items": [
    {
      "id": 1,
      "fact": "Olivier aime le café",
      "confidence": 0.95,
      "created_at": "2026-11-11T15:00:00Z",
      "updated_at": "2026-11-11T15:00:00Z",
      "source": "command"
    },
    {
      "id": 2,
      "fact": "La température idéale est 22°C",
      "confidence": 0.85,
      "created_at": "2026-11-11T14:00:00Z",
      "updated_at": "2026-11-11T14:00:00Z",
      "source": "autonomy"
    }
  ],
  "total": 2
}
```

---

### `DELETE /api/memory/{fid}`

Supprime un fait de la mémoire.

**Requête** :
```bash
curl -X DELETE http://localhost:8099/api/memory/1
```

**Réponse** :
```json
{
  "status": "success",
  "message": "Fait supprimé",
  "id": 1
}
```

---

## 📝 Endpoints de Configuration

### `GET /api/config`

Obtient la configuration actuelle.

**Requête** :
```bash
curl http://localhost:8099/api/config
```

**Réponse** :
```json
{
  "version": "3.9.0",
  "options": {
    "gemini_api_key": "***",
    "gemini_model": "gemini-3.6-flash",
    "speak_service": "",
    "actions_enabled": true,
    "autonomy_enabled": true,
    "autonomy_interval": 30,
    "vision_enabled": false
  }
}
```

⚠️ **Note** : Les clés sensibles (comme `gemini_api_key`) sont masquées.

---

## ⚡ Endpoints de Performance

### `GET /api/performance`

Obtient les métriques de performance.

**Requête** :
```bash
curl http://localhost:8099/api/performance
```

**Réponse** :
```json
{
  "cache": {
    "lru_cache": {
      "size": 42,
      "max_size": 100,
      "hit_rate": 0.85,
      "hits": 357,
      "misses": 63
    },
    "ttl_cache": {
      "size": 15,
      "max_size": 50,
      "hit_rate": 0.75,
      "hits": 120,
      "misses": 40
    }
  },
  "connection_pool": {
    "database": {
      "total_connections": 5,
      "available_connections": 3,
      "in_use_connections": 2,
      "max_connections": 10
    },
    "http": {
      "total_connections": 20,
      "available_connections": 15,
      "in_use_connections": 5,
      "max_connections": 100
    }
  },
  "batch_processor": {
    "items_processed": 100,
    "batches_completed": 10,
    "avg_batch_size": 10,
    "processing_time_avg": 150,
    "processing_time_max": 500
  },
  "performance_monitor": {
    "metrics_collected": 294,
    "alerts_triggered": 2,
    "snapshots": 10
  },
  "optimizer": {
    "optimizations_performed": 5,
    "recommendations": [
      {
        "parameter": "batch_size",
        "recommended_value": 15,
        "reason": "Based on recent optimizations"
      }
    ]
  }
}
```

---

### `GET /api/performance/alerts`

Liste toutes les alertes de performance.

**Requête** :
```bash
curl http://localhost:8099/api/performance/alerts
```

**Réponse** :
```json
{
  "alerts": [
    {
      "id": "alert_abc123",
      "name": "high_cpu_usage",
      "level": "warning",
      "message": "CPU usage > 80%",
      "metric_name": "cpu_usage",
      "metric_value": 85.5,
      "threshold": 80.0,
      "timestamp": "2026-11-11T15:00:00Z",
      "actions_triggered": [
        {
          "type": "notification",
          "target": "phone_olivier",
          "message": "CPU usage élevé détecté"
        }
      ]
    }
  ],
  "total": 1
}
```

---

## 📋 Schémas de Données

### Action

```json
{
  "domain": "string",
  "service": "string",
  "entity_id": "string",
  "data": {},
  "status": "pending|completed|failed",
  "timestamp": "ISO8601",
  "error": "string (optionnel)"
}
```

### Command

```json
{
  "id": "string",
  "prompt": "string",
  "response": "string",
  "actions": [Action],
  "confidence": 0.0-1.0,
  "processing_time": integer,
  "timestamp": "ISO8601",
  "user": "string (optionnel)",
  "speak": boolean
}
```

### Detection

```json
{
  "id": "string",
  "camera_id": "string",
  "label": "string",
  "confidence": 0.0-1.0,
  "timestamp": "ISO8601",
  "duration": float,
  "bounding_box": {
    "x": float,
    "y": float,
    "width": float,
    "height": float
  },
  "image_url": "string",
  "video_url": "string",
  "actions_triggered": [Action]
}
```

### Rule

```json
{
  "name": "string",
  "description": "string",
  "conditions": [Condition],
  "actions": [Action],
  "priority": integer,
  "status": "active|inactive",
  "last_triggered": "ISO8601 (optionnel)",
  "trigger_count": integer
}
```

### Condition

```json
{
  "entity": "string",
  "state": "string",
  "operator": "==|!=|>|<|>=|<=",
  "value": any,
  "time": "ISO8601 (optionnel)",
  "duration": integer (optionnel)
}
```

---

## 🐛 Codes d'Erreur

| Code | Description | Solution |
|------|-------------|----------|
| `400` | Requête invalide | Vérifiez les paramètres de la requête |
| `401` | Non autorisé | Vérifiez l'authentification |
| `403` | Accès interdit | Vérifiez les permissions |
| `404` | Ressource introuvable | Vérifiez l'URL |
| `405` | Méthode non autorisée | Vérifiez la méthode HTTP |
| `408` | Timeout | Réessayez plus tard |
| `429` | Trop de requêtes | Attendez avant de réessayer |
| `500` | Erreur interne du serveur | Vérifiez les logs |
| `502` | Mauvaise passerelle | Vérifiez la connexion à Home Assistant |
| `503` | Service indisponible | Réessayez plus tard |

### Erreurs Spécifiques

| Code | Erreur | Description |
|------|--------|-------------|
| `1001` | `GeminiUnavailable` | L'API Gemini est indisponible |
| `1002` | `InvalidApiKey` | La clé API Gemini est invalide |
| `1003` | `QuotaExceeded` | Le quota de requêtes a été dépassé |
| `2001` | `HaConnectionError` | Impossible de se connecter à Home Assistant |
| `2002` | `InvalidToken` | Le token Home Assistant est invalide |
| `2003` | `EntityNotFound` | L'entité n'existe pas |
| `3001` | `AutonomyDisabled` | L'autonomie est désactivée |
| `3002` | `RuleNotFound` | La règle n'existe pas |
| `4001` | `VoiceDisabled` | La voix est désactivée |
| `4002` | `InvalidPin` | Le code PIN est invalide |

---

## 📌 Bonnes Pratiques

### 1. Utilisation des Tokens

- **Ne partagez jamais votre token** avec des tiers
- **Changez régulièrement votre token** pour des raisons de sécurité
- **Utilisez des tokens différents** pour différentes applications

### 2. Gestion des Erreurs

- **Gérez toujours les erreurs** dans votre code
- **Utilisez des retries** pour les requêtes temporairement indisponibles
- **Implémentez des fallbacks** pour les fonctionnalités critiques

### 3. Optimisation des Requêtes

- **Utilisez le cache** pour éviter les requêtes répétitives
- **Regroupez les requêtes** quand c'est possible
- **Évitez les requêtes inutiles** pendant les périodes de faible activité

### 4. Sécurité

- **Utilisez HTTPS** pour toutes les communications
- **Validez toujours les entrées** utilisateur
- **Sanitizez les données** avant de les afficher
- **Limitez les permissions** au minimum nécessaire

### 5. Monitoring

- **Surveillez les performances** de l'API
- **Configurez des alertes** pour les erreurs critiques
- **Journalisez toutes les requêtes** pour le dépannage

---

## 📚 Exemples Complets

### Exemple 1 : Automatisation avec Webhooks

```python
import requests
import json

# Configuration
JARVIS_URL = "http://localhost:8099"
API_TOKEN = "VOTRE_TOKEN"

# Envoyer une commande
def send_command(prompt, speak=False):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_TOKEN}"
    }
    
    data = {
        "prompt": prompt,
        "speak": speak
    }
    
    response = requests.post(
        f"{JARVIS_URL}/api/command",
        headers=headers,
        data=json.dumps(data)
    )
    
    return response.json()

# Exemple d'utilisation
result = send_command("Allume la lumière du salon")
print(result)
```

### Exemple 2 : Vérification des Mises à Jour

```python
import requests

def check_updates():
    response = requests.get("http://localhost:8099/api/version/check")
    data = response.json()
    
    if data["status"] == "update_available":
        print(f"Nouvelle version {data['latest_version']} disponible!")
        print("Changements:")
        for change in data["changelog"]:
            print(f"- {change}")
    else:
        print("L'application est à jour.")

check_updates()
```

### Exemple 3 : Monitoring des Performances

```python
import requests
import time

def monitor_performance():
    while True:
        response = requests.get("http://localhost:8099/api/diagnostic")
        data = response.json()
        
        print(f"CPU: {data['system']['cpu_usage']}%")
        print(f"Mémoire: {data['system']['memory_usage']}%")
        print(f"Commandes aujourd'hui: {data['jarvis']['commands_today']}")
        print("-" * 50)
        
        time.sleep(60)

monitor_performance()
```

### Exemple 4 : Gestion des Propositions

```python
import requests

def list_proposals():
    response = requests.get("http://localhost:8099/api/proposals")
    data = response.json()
    
    for proposal in data["proposals"]:
        print(f"ID: {proposal['id']}")
        print(f"Description: {proposal['description']}")
        print(f"Actions: {len(proposal['actions'])}")
        print("-" * 50)
        
        # Approuver ou rejeter
        action = input("Approuver (a) ou Rejeter (r) ? ").lower()
        
        if action == "a":
            requests.post(f"http://localhost:8099/api/proposals/{proposal['id']}/approve")
            print("Proposition approuvée")
        elif action == "r":
            requests.post(f"http://localhost:8099/api/proposals/{proposal['id']}/reject")
            print("Proposition rejetée")

list_proposals()
```

---

## 📞 Support

Si vous avez des questions ou rencontrez des problèmes avec l'API :

- **GitHub Issues** : [https://github.com/atila593/jarvis-ha-control/issues](https://github.com/atila593/jarvis-ha-control/issues)
- **Discussions** : [https://github.com/atila593/jarvis-ha-control/discussions](https://github.com/atila593/jarvis-ha-control/discussions)
- **Email** : boucaolivier@gmail.com

---

**Bonne utilisation de l'API Jarvis HA Control ! 🚀**
