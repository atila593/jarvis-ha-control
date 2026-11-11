# 📚 Documentation Technique

Ce document fournit des informations techniques detaillees sur Jarvis HA Control.

## 📋 Table des Matieres

- [🎯 Design Patterns](#-design-patterns)
- [⚙️ Implementation Details](#️-implementation-details)
- [📊 Performance Optimization](#-performance-optimization)
- [🔒 Security Considerations](#-security-considerations)
- [🧪 Testing Strategy](#-testing-strategy)
- [📦 Deployment](#-deployment)
- [🔄 Migration Guide](#-migration-guide)

---

## 🎯 Design Patterns

### 1. Singleton Pattern

Utilise pour les instances globales :
- VersionManager
- CacheManager
- PerformanceMonitor

```python
class Singleton:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

### 2. Factory Pattern

Utilise pour la creation des agents :

```python
class AgentFactory:
    @staticmethod
    def create_agent(agent_type, **kwargs):
        if agent_type == "conversation":
            return ConversationAgent(**kwargs)
        elif agent_type == "decision":
            return DecisionAgent(**kwargs)
        # ...
```

### 3. Observer Pattern

Utilise pour les evenements et le monitoring :

```python
class EventBus:
    def __init__(self):
        self._observers = {}
    
    def subscribe(self, event_type, observer):
        if event_type not in self._observers:
            self._observers[event_type] = []
        self._observers[event_type].append(observer)
    
    def publish(self, event_type, data):
        for observer in self._observers.get(event_type, []):
            observer.update(data)
```

### 4. Strategy Pattern

Utilise pour les strategies de cache :

```python
class CacheStrategy(ABC):
    @abstractmethod
    async def get(self, key):
        pass
    
    @abstractmethod
    async def set(self, key, value):
        pass

class LRUStrategy(CacheStrategy):
    # Implementation LRU
    
class TTLStrategy(CacheStrategy):
    # Implementation TTL
```

### 5. Command Pattern

Utilise pour l'execution des actions :

```python
class Command(ABC):
    @abstractmethod
    async def execute(self):
        pass

class TurnOnLightCommand(Command):
    def __init__(self, entity_id):
        self.entity_id = entity_id
    
    async def execute(self):
        await ha_client.call_service("light", "turn_on", {"entity_id": self.entity_id})
```

---

## ⚙️ Implementation Details

### 1. Module Structure

```
jarvis_ha_control/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration
│   ├── assistant/
│   │   ├── __init__.py
│   │   ├── gemini_engine.py # Gemini integration
│   │   └── prompts.py       # System prompts
│   ├── autonomy/
│   │   ├── __init__.py
│   │   ├── engine.py        # Autonomy engine
│   │   ├── rules.py         # Rules management
│   │   ├── confidence.py    # Confidence system
│   │   ├── ha.py            # HA REST client
│   │   ├── ha_websocket.py  # HA WebSocket client
│   │   ├── store.py         # SQLite storage
│   │   ├── vision.py        # Frigate integration
│   │   ├── engineer.py      # Entity modification
│   │   └── access.py        # Access control
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py  # Agent orchestrator
│   │   ├── conversation_agent.py
│   │   ├── decision_agent.py
│   │   ├── action_agent.py
│   │   ├── monitoring_agent.py
│   │   └── security_agent.py
│   ├── performance/
│   │   ├── __init__.py
│   │   ├── cache.py         # Caching
│   │   ├── connection_pool.py
│   │   ├── batch_processor.py
│   │   ├── performance_monitor.py
│   │   └── optimizer.py     # Auto-optimization
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── toolbox.py
│   │   ├── actions.py
│   │   ├── speak.py
│   │   ├── status.py
│   │   ├── presence.py
│   │   └── sys_diagnose.py
│   └── version.py           # Version management
├── tests/
│   ├── test_agents.py
│   ├── test_performance.py
│   ├── test_integration.py
│   └── test_version.py
└── docs/
```

### 2. Key Components

#### FastAPI Application

```python
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager

app = FastAPI(title="Jarvis HA Control", version="3.9.0")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialization
    yield
    # Cleanup

app = FastAPI(lifespan=lifespan)
```

#### Autonomy Engine

```python
class AutonomyEngine:
    def __init__(self, store, settings, params):
        self.store = store
        self.settings = settings
        self.params = params
        self.rules = []
        self.running = False
    
    async def run(self):
        while self.running:
            await self.check_rules()
            await asyncio.sleep(self.settings.interval)
    
    async def check_rules(self):
        for rule in self.rules:
            if await rule.check_conditions():
                await rule.execute_actions()
```

#### Orchestrator

```python
class Orchestrator:
    def __init__(self, conversation_agent, decision_agent, action_agent):
        self.conversation = conversation_agent
        self.decision = decision_agent
        self.action = action_agent
    
    async def process_request(self, request):
        # Step 1: Process conversation
        response = await self.conversation.process_message(request)
        
        # Step 2: Make decision
        decision = await self.decision.make_decision(response)
        
        # Step 3: Execute action
        action = await self.action.execute(decision)
        
        return action
```

---

## 📊 Performance Optimization

### 1. Caching Strategy

**LRU Cache** : Least Recently Used
- Ideal pour les donnees frequentement acces
- Limite la taille du cache
- Eviction automatique

**TTL Cache** : Time To Live
- Ideal pour les donnees temporaires
- Expiration automatique
- Cleanup periodique

**Cache Manager** : Gestion centralisee
- Multiple caches avec differentes configurations
- Statistiques de cache
- Cleanup automatique

### 2. Connection Pooling

**Database Connection Pool** :
- Reutilise les connexions SQLite
- Reduit la latence
- Limite le nombre de connexions

**HTTP Connection Pool** :
- Reutilise les connexions HTTP
- Gestion avec aiohttp
- Optimisation pour les appels repetitifs

### 3. Batch Processing

**Batch Processor** :
- Traite plusieurs elements en parallele
- Gestion de la concurrence
- Retry automatique
- Optimisation des ressources

**Action Batcher** :
- Regroupe les actions HA
- Execution parallele
- Reduction des appels API

### 4. Performance Monitoring

**Metrics Collector** :
- Collection periodique des metriques
- CPU, Memoire, Disque, Reseau
- Metriques personnalisees

**Performance Monitor** :
- Surveillance en temps reel
- Alertes automatiques
- Snapshots periodiques
- Rapports de performance

**Performance Optimizer** :
- Optimisation automatique
- Ajustement des parametres
- Recommendations
- Historique des optimisations

---

## 🔒 Security Considerations

### 1. Authentication

- Integration avec l'authentification HA
- Tokens API optionnels
- Voice PIN pour l'acces vocal

### 2. Authorization

- Systeme de roles (admin, user, guest)
- Permissions fine-grained
- Validation des actions

### 3. Data Protection

- Chiffrement des communications
- Stockage securise des secrets
- Audit complet des actions

### 4. Input Validation

- Validation de toutes les entrees
- Sanitization des sorties
- Protection contre les injections

---

## 🧪 Testing Strategy

### 1. Unit Tests

- Tests de chaque fonction
- Tests des classes
- Tests des modules

```python
# Example unit test
@pytest.mark.asyncio
async def test_cache_set_get():
    cache = LRUCache(max_size=10)
    await cache.set("key1", "value1")
    assert await cache.get("key1") == "value1"
```

### 2. Integration Tests

- Tests des interactions entre modules
- Tests des workflows complets
- Tests des APIs

```python
# Example integration test
@pytest.mark.asyncio
async def test_full_workflow():
    # Setup
    conversation = ConversationAgent()
    decision = DecisionAgent()
    action = ActionAgent()
    orchestrator = Orchestrator(conversation, decision, action)
    
    # Test
    result = await orchestrator.process_request("Allume la lumiere")
    assert result is not None
```

### 3. Stress Tests

- Tests sous charge elevee
- Tests de performance
- Tests de robustesse

```python
# Example stress test
@pytest.mark.asyncio
async def test_concurrent_operations():
    cache = LRUCache(max_size=1000)
    
    async def cache_operation(i):
        await cache.set(f"key_{i}", f"value_{i}")
        return await cache.get(f"key_{i}")
    
    tasks = [cache_operation(i) for i in range(100)]
    results = await asyncio.gather(*tasks)
    assert all(results)
```

### 4. End-to-End Tests

- Tests complets du systeme
- Tests avec HA reel
- Tests avec l'interface utilisateur

---

## 📦 Deployment

### 1. Development Deployment

```bash
# Clone the repository
git clone https://github.com/atila593/jarvis-ha-control.git
cd jarvis-ha-control

# Install dependencies
poetry install

# Run in development mode
export JARVIS_DEV=true
python -m jarvis_ha_control.app.main
```

### 2. Production Deployment

```bash
# Via HACS (recommended)
# or manual installation

# Configure in Home Assistant
# Restart Home Assistant
```

### 3. Docker Deployment

```bash
# Build the image
docker build -t jarvis-ha-control .

# Run the container
docker run -d \
  --name jarvis-ha-control \
  -p 8099:8099 \
  -v /path/to/config:/config \
  -e HA_API_URL=http://homeassistant:8123 \
  -e SUPERVISOR_TOKEN=your_token \
  jarvis-ha-control
```

---

## 🔄 Migration Guide

### From 3.0.x to 3.9.0

1. **Backup your configuration**
   ```bash
   cp /config/jarvis-ha-control/config.yaml /config/jarvis-ha-control/config.yaml.backup
   ```

2. **Update the code**
   ```bash
   cd /config/jarvis-ha-control
   git pull origin main
   ```

3. **Update configuration**
   - Add new options from the updated config.yaml
   - Review and update your settings

4. **Test the update**
   ```bash
   # Test in development mode first
   export JARVIS_DEV=true
   python -m jarvis_ha_control.app.main
   ```

5. **Deploy to production**
   ```bash
   # Restart AppDaemon
   sudo systemctl restart appdaemon
   ```

### Version-Specific Migrations

#### 3.3.0 -> 3.3.1
Fixed pickle serialization error. No migration needed.

#### 3.4.0 -> 3.5.0
Added Agents module. Update your configuration to include agent settings.

#### 3.6.0 -> 3.7.0
Added Performance module. Enable performance monitoring in environment variables.

#### 3.7.0 -> 3.8.0
Added Version module. No migration needed.

#### 3.8.0 -> 3.9.0
Added complete documentation. No migration needed.

---

## 📚 Additional Resources

- [Installation Guide](INSTALLATION.md)
- [Configuration Guide](CONFIGURATION.md)
- [User Guide](USER_GUIDE.md)
- [API Reference](API_REFERENCE.md)
- [Architecture](ARCHITECTURE.md)
