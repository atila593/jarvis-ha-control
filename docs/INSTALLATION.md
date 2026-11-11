# 📥 Guide d'Installation

Ce guide vous explique comment installer et configurer Jarvis HA Control sur votre système Home Assistant.

---

## 📋 Prérequis

Avant d'installer Jarvis HA Control, assurez-vous que votre système répond aux exigences suivantes :

### Exigences Système

| Composant | Version Minimum | Recommandé |
|-----------|----------------|-----------|
| Home Assistant | 2024.12.0 | 2025.x.x |
| Python | 3.12.0 | 3.12+ |
| AppDaemon | 4.4.0 | 4.5.0+ |
| Mémoire RAM | 512 Mo | 2 Go+ |
| Espace Disque | 100 Mo | 1 Go+ |

### Dépendances Python

Les dépendances principales sont :
- `fastapi` - Framework web
- `httpx` - Client HTTP async
- `aiohttp` - Client HTTP async alternatif
- `google-generativeai` - SDK Gemini
- `psutil` - Monitoring système
- `sqlite3` - Base de données intégrée

---

## 🚀 Méthodes d'Installation

### Méthode 1 : Via HACS (Recommandé)

HACS (Home Assistant Community Store) est la méthode la plus simple pour installer Jarvis HA Control.

#### Étapes :

1. **Installer HACS** (si ce n'est pas déjà fait) :
   - Allez dans **Paramètres** > **Add-ons**
   - Cliquez sur **➕ Ajouter un add-on**
   - Recherchez "HACS" et installez-le
   - Redémarrez Home Assistant

2. **Ajouter le dépôt personnalisé** :
   - Allez dans **HACS** > **Paramètres**
   - Cliquez sur **Dépôts personnalisés**
   - Ajoutez un nouveau dépôt :
     - **URL** : `https://github.com/atila593/jarvis-ha-control`
     - **Catégorie** : `AppDaemon`
     - **Type** : `Integration`

3. **Installer Jarvis HA Control** :
   - Allez dans **HACS** > **Intégrations**
   - Recherchez "Jarvis HA Control"
   - Cliquez sur **Installer**
   - Redémarrez Home Assistant

4. **Configurer** :
   - Allez dans **Paramètres** > **AppDaemon**
   - Ajoutez une nouvelle application
   - Sélectionnez Jarvis HA Control
   - Configurez les paramètres dans `config.yaml`

---

### Méthode 2 : Installation Manuelle

Si vous préférez une installation manuelle, suivez ces étapes :

#### Étapes :

1. **Accéder à votre système Home Assistant** :
   ```bash
   # Via SSH ou Terminal
   ssh homeassistant@[IP_HOME_ASSISTANT]
   ```

2. **Cloner le dépôt** :
   ```bash
   cd /config
   git clone https://github.com/atila593/jarvis-ha-control.git
   ```

3. **Créer la structure de fichiers** :
   ```bash
   mkdir -p /config/jarvis-ha-control/apps/jarvis_ha_control
   cp -r /config/jarvis-ha-control/jarvis_ha_control/* /config/jarvis-ha-control/apps/jarvis_ha_control/
   cp /config/jarvis-ha-control/config.yaml /config/jarvis-ha-control/apps/jarvis_ha_control/
   ```

4. **Configurer AppDaemon** :
   - Éditez `/config/appdaemon.yaml` :
     ```yaml
     appdaemon:
       plugins:
         HASS:
           type: hass
           ha_url: http://localhost:8123
           token: YOUR_LONG_LIVED_TOKEN
       
       app_dir: /config/jarvis-ha-control/apps
     ```

5. **Créer le fichier de configuration** :
   - Copiez `config.yaml.example` vers `config.yaml` :
     ```bash
     cd /config/jarvis-ha-control/apps/jarvis_ha_control
     cp config.yaml.example config.yaml
     ```

6. **Configurer les paramètres** :
   - Éditez `config.yaml` avec vos paramètres :
     ```yaml
     options:
       gemini_api_key: "VOTRE_CLE_API_GEMINI"
       speak_service: "notify.mobile_app"
       speak_targets: ["phone_olivier"]
       autonomy_enabled: true
     ```

7. **Redémarrer AppDaemon** :
   ```bash
   sudo systemctl restart appdaemon
   ```

8. **Vérifier l'installation** :
   - Allez dans **Paramètres** > **AppDaemon**
   - Vérifiez que Jarvis HA Control est en cours d'exécution
   - Accédez à l'interface : `http://[IP_HOME_ASSISTANT]:8099`

---

### Méthode 3 : Docker (Pour Développement)

Si vous souhaitez développer ou tester Jarvis HA Control en local :

#### Étapes :

1. **Cloner le dépôt** :
   ```bash
   git clone https://github.com/atila593/jarvis-ha-control.git
   cd jarvis-ha-control
   ```

2. **Créer un fichier Dockerfile** :
   ```dockerfile
   FROM python:3.12-slim
   
   WORKDIR /app
   
   COPY . .
   
   RUN pip install poetry && \
       poetry config virtualenvs.create false && \
       poetry install --no-dev
   
   EXPOSE 8099
   
   CMD ["python", "-m", "jarvis_ha_control.app.main"]
   ```

3. **Construire l'image** :
   ```bash
   docker build -t jarvis-ha-control .
   ```

4. **Exécuter le conteneur** :
   ```bash
   docker run -d \
     --name jarvis-ha-control \
     -p 8099:8099 \
     -v $(pwd)/config:/config \
     -e HA_API_URL=http://host.docker.internal:8123 \
     -e SUPERVISOR_TOKEN=your_supervisor_token \
     -e GEMINI_API_KEY=your_gemini_api_key \
     jarvis-ha-control
   ```

5. **Accéder à l'application** :
   - Ouvrez votre navigateur : `http://localhost:8099`

---

### Méthode 4 : Python Direct (Pour Développement)

Pour exécuter Jarvis HA Control directement avec Python :

#### Étapes :

1. **Cloner le dépôt** :
   ```bash
   git clone https://github.com/atila593/jarvis-ha-control.git
   cd jarvis-ha-control
   ```

2. **Installer les dépendances** :
   ```bash
   # Avec Poetry
   poetry install
   
   # Avec pip
   pip install -r requirements.txt
   ```

3. **Configurer l'environnement** :
   ```bash
   cp .env.example .env
   # Éditer .env avec vos paramètres
   ```

4. **Exécuter l'application** :
   ```bash
   export JARVIS_DEV=true
   python -m jarvis_ha_control.app.main
   ```

5. **Accéder à l'application** :
   - Ouvrez votre navigateur : `http://localhost:8099`

---

## ✅ Vérification de l'Installation

### 1. Vérifier que l'application est en cours d'exécution

```bash
# Via AppDaemon
curl http://localhost:8099/api/status
```

Réponse attendue :
```json
{
  "version": "3.9.0",
  "status": "running",
  "autonomy_enabled": false,
  "autonomy_status": "inactive",
  "websocket_connected": false,
  "last_command": null,
  "commands_today": 0,
  "actions_today": 0
}
```

### 2. Tester une commande simple

```bash
curl -X POST http://localhost:8099/api/command \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Bonjour", "speak": false}'
```

Réponse attendue :
```json
{
  "response": "Bonjour ! Comment puis-je vous aider aujourd'hui ?",
  "actions": []
}
```

### 3. Vérifier les logs

```bash
# Logs AppDaemon
tail -f /config/appdaemon/logs/appdaemon.log

# Logs Jarvis
tail -f /config/jarvis-ha-control/logs/jarvis.log
```

---

## 🔧 Configuration Initiale

### 1. Obtenir une clé API Gemini

1. Allez sur [Google AI Studio](https://aistudio.google.com/)
2. Créez un nouveau projet ou sélectionnez-en un existant
3. Allez dans **API Keys**
4. Générez une nouvelle clé API
5. Copiez la clé dans votre configuration

### 2. Obtenir un token Home Assistant

1. Allez dans votre instance Home Assistant
2. Allez dans **Paramètres** > **Personnes**
3. Sélectionnez votre utilisateur
4. Faites défiler vers le bas et cliquez sur **Créer un token**
5. Donnez un nom au token (ex: "Jarvis HA Control")
6. Copiez le token généré

### 3. Configurer `config.yaml`

Éditez le fichier `config.yaml` avec vos paramètres :

```yaml
options:
  # API Gemini (requis)
  gemini_api_key: "VOTRE_CLE_API_GEMINI"
  gemini_model: gemini-3.6-flash
  gemini_fallback_model: gemini-3.5-flash
  
  # Réponse vocale (optionnel)
  speak_service: "notify.mobile_app"
  speak_targets: ["phone_olivier"]
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
    - switch
  
  # Autonomie
  autonomy_enabled: false
  autonomy_interval: 30
  autonomy_rules: []
  
  # Présence
  presence_prefix: ""
  presence_zone_names: []
  
  # Disponibilité
  quiet_start: "23:00"
  quiet_end: "07:00"
```

---

## 🛠️ Configuration Avancée

### 1. Configurer les agents

Pour activer les agents IA :

```yaml
options:
  autonomy_enabled: true
  
  # Règles d'autonomie
  autonomy_rules:
    - "allumer_lumieres_soir"
    - "eteindre_lumieres_nuit"
  
  # Règles automatiques
  auto_rules:
    - "if sun.sun below_horizon and binary_sensor.presence_living_room on then light.turn_on light.living_room"
  
  # Approbateurs
  approvers:
    - "person.olivier"
```

### 2. Configurer la vision (Frigate)

```yaml
options:
  vision_enabled: true
  frigate_url: "http://[IP_FRIGATE]:5000"
  vision_labels:
    - person
    - dog
    - cat
  vision_cameras:
    - camera.front_door
    - camera.backyard
  vision_api_key: "VOTRE_CLE_API_FRIGATE"
  vision_daily_budget: 60
  vision_cooldown_minutes: 5
```

### 3. Configurer le monitoring

```yaml
# Variables d'environnement
PERFORMANCE_MONITORING_ENABLED: true
CACHE_ENABLED: true
BATCH_PROCESSING_ENABLED: true
```

### 4. Configurer les rôles utilisateurs

```yaml
options:
  user_roles:
    - "olivier:admin"
    - "marie:user"
    - "enfant:guest"
  voice_pin: "1234"
  voice_enabled: true
```

---

## 🔄 Mise à Jour

### Via HACS

1. Allez dans **HACS** > **Intégrations**
2. Trouvez Jarvis HA Control
3. Cliquez sur **Mettre à jour**
4. Redémarrez Home Assistant

### Manuellement

1. Arrêtez l'application :
   ```bash
   sudo systemctl stop appdaemon
   ```

2. Mettre à jour le code :
   ```bash
   cd /config/jarvis-ha-control
   git pull origin main
   ```

3. Copier les nouveaux fichiers :
   ```bash
   cp -r jarvis_ha_control/* /config/jarvis-ha-control/apps/jarvis_ha_control/
   cp config.yaml /config/jarvis-ha-control/apps/jarvis_ha_control/
   ```

4. Redémarrer l'application :
   ```bash
   sudo systemctl start appdaemon
   ```

---

## 🎯 Vérification Finale

1. **Vérifier la version** :
   ```bash
   curl http://localhost:8099/api/version
   ```

2. **Vérifier les mises à jour** :
   ```bash
   curl http://localhost:8099/api/version/check
   ```

3. **Tester une commande complexe** :
   ```bash
   curl -X POST http://localhost:8099/api/command \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Allume toutes les lumières du rez-de-chaussée", "speak": false}'
   ```

4. **Vérifier le monitoring** :
   ```bash
   curl http://localhost:8099/api/diagnostics
   ```

---

## 🐛 Dépannage

### Problèmes Courants

#### 1. L'application ne démarre pas

**Symptômes** :
- AppDaemon ne démarre pas
- Erreurs dans les logs

**Solutions** :
- Vérifiez les logs : `tail -f /config/appdaemon/logs/appdaemon.log`
- Vérifiez que Python 3.12+ est installé
- Vérifiez que toutes les dépendances sont installées
- Vérifiez que le fichier `config.yaml` est valide

#### 2. Erreur de connexion à l'API Gemini

**Symptômes** :
```
GeminiUnavailable: Failed to connect to Gemini API
```

**Solutions** :
- Vérifiez que votre clé API est correcte
- Vérifiez que vous avez du crédit sur votre compte Google Cloud
- Vérifiez que votre réseau autorise les connexions vers `generativelanguage.googleapis.com`

#### 3. Erreur de connexion à Home Assistant

**Symptômes** :
```
Failed to connect to Home Assistant API
```

**Solutions** :
- Vérifiez que l'URL de Home Assistant est correcte
- Vérifiez que le token est valide
- Vérifiez que Home Assistant est en cours d'exécution

#### 4. Problèmes de permissions

**Symptômes** :
```
Permission denied
```

**Solutions** :
- Vérifiez les permissions des fichiers : `chmod -R 755 /config/jarvis-ha-control`
- Vérifiez que l'utilisateur AppDaemon a accès aux fichiers

---

## 📚 Ressources Supplémentaires

- [Documentation Technique](TECHNICAL.md)
- [Guide de Configuration](CONFIGURATION.md)
- [Guide Utilisateur](USER_GUIDE.md)
- [API Reference](API_REFERENCE.md)
- [Architecture](ARCHITECTURE.md)

---

## 🙏 Support

Si vous rencontrez des problèmes qui ne sont pas couverts par ce guide :

- **GitHub Issues** : [https://github.com/atila593/jarvis-ha-control/issues](https://github.com/atila593/jarvis-ha-control/issues)
- **Discussions** : [https://github.com/atila593/jarvis-ha-control/discussions](https://github.com/atila593/jarvis-ha-control/discussions)
- **Email** : boucaolivier@gmail.com

---

**Bonne installation ! 🎉**
