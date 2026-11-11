
## 4.0.0
- **Dashboard futuriste** : Design IA autonome sans scroll avec animations et effets lumineux
- **Sélecteur d'entités dropdown** : Menu déroulant intelligent avec recherche et catégories pour toutes les entités HA
- **Zone d'activité en temps réel** : Affichage live des actions en cours, dernières actions et décisions autonomes
- **Configuration avec menus déroulants** : Sélection facile des entités dans l'interface de configuration de l'addon
- **Design tactile-friendly** : Boutons adaptés aux écrans tactiles avec taille minimale de 48x48px
- **Design responsive** : Adapté aux écrans mobile, tablette et desktop
- **Nouveaux endpoints API** : /api/entities et /api/realtime-activity pour le dashboard
- **Configuration améliorée** : Fichier config.json avec sélecteurs natifs pour Home Assistant
- **Catégorisation automatique** : Les entités sont automatiquement classées par type (Lumières, Volets, Caméras, etc.)
- **Boutons d'action rapide** : Accès direct aux commandes courantes (Tout allumer, Tout éteindre, etc.)
- **Amélioration UX** : Meilleure expérience utilisateur avec feedback visuel en temps réel

## 3.9.0
- **Documentation complete** : Documentation technique et utilisateur complete (README, INSTALLATION, CONFIGURATION, USER_GUIDE, API_REFERENCE, ARCHITECTURE, TECHNICAL)
- **Revue finale** : Revue complete du code, optimisation et validation
- **Systeme de mise a jour automatique** : Detection et notification des nouvelles versions via GitHub API
- **Integration HA optimisee** : Connexion WebSocket et REST optimisee avec cache et pool de connexions
- **Architecture modulaire** : Separation claire des responsabilites avec design patterns modernes
- **Tests complets** : Tests unitaires, d integration, de stress et end-to-end
- **Performance maximale** : Cache LRU/TTL, pool de connexions, batch processing, monitoring temps reel
- **Securite renforcee** : Systeme de roles, permissions, audit complet et validation des entrees
- **Système de versionnement** : Gestion des versions avec changelog et features
- **Notifications intelligentes** : Alertes pour les mises a jour, erreurs et evenements importants

## 3.8.0
- **Tests d'integration complete** : Tests complets pour tous les modules et leur integration
- **Systeme de versionnement** : Gestion des versions avec detection automatique des mises a jour
- **Notifications de mise a jour** : Notifications en temps reel pour les nouvelles versions
- **Integration complete des modules** : Tous les modules (Agents, Performance) sont entierement integrés
- **Tests de stress** : Tests de performance et de robustesse sous charge
- **Tests d'erreur** : Gestion complete des erreurs et recuperation
- **API de version** : Endpoints API pour verifier la version et les mises a jour
- **Système de cache unifié** : Integration du cache avec tous les composants
- **Traitement par lots optimisé** : Batch processing intégré avec les agents
- **Monitoring complet** : Surveillance complete du systeme avec alertes

## 3.7.0
- **Optimisation des performances** : Module complet pour maximiser la reactivite et l'efficacite
- **Mise en cache** : LRU Cache, TTL Cache, CacheManager pour reduire la latence
- **Pool de connexions** : ConnectionPool, DatabaseConnectionPool, HTTPConnectionPool pour une gestion efficace des ressources
- **Traitement par lots** : BatchProcessor, ActionBatcher pour un traitement optimise des actions
- **Monitoring des performances** : MetricsCollector, PerformanceMonitor pour un suivi en temps reel
- **Optimisation automatique** : PerformanceOptimizer avec ajustement dynamique des parametres
- **Caching des requetes** : Reduit les appels repetitifs a Home Assistant
- **Connexions reusees** : Pool de connexions SQLite et HTTP pour une meilleure efficacite
- **Traitement parallele** : Execution par lots avec gestion de la concurrence

## 3.6.0
- **MonitoringAgent** : Surveillance complete du systeme (CPU, memoire, disque, reseau)
- **SecurityAgent** : Gestion des utilisateurs, roles, permissions et authentification
- **Alertes intelligentes** : Detection automatique des anomalies avec seuils configurables
- **Audit complet** : Journalisation de toutes les actions de securite
- **Protection renforcee** : Verrouillage des utilisateurs apres trop de tentatives
- **Gestion des sessions** : Sessions avec timeout et invalidation


## 3.5.0
- **Agents IA** : ConversationAgent, DecisionAgent, ActionAgent, Orchestrator pour une autonomie complète
- **Workflow automatisé** : Conversation → Décision → Action en un seul flux
- **Gestion des priorités** : File d attente avec priorisation des actions
- **Sécurité renforcée** : Vérification des préconditions et postconditions
- **Rollback automatique** : Annulation des actions en cas d échec
- **Tests unitaires** : Tests complets pour tous les agents

## 3.3.1
- **FIX: Correction bug pickle** : Remplacement des threading.Lock() par des transactions SQLite + implémentation de __getstate__/__setstate__ pour permettre la sérialisation de l'objet Store

## 3.3.0
- **Système de confiance** : Score de confiance dynamique (0.0-1.0) pour les actions autonomes
- **Règles dynamiques** : Actions basées sur la présence, l'heure, la météo et l'état du système
- **Mémoire des actions** : Apprentissage continu des préférences utilisateur
- **Intégration WebSocket** : Détection des événements Home Assistant en temps réel (< 1s de latence)

## 3.2.0
- **Polling optimisé** : Intervalle adaptatif (5-30s) selon l'activité
- **Polling ciblé** : Récupération uniquement des entités surveillées
- **Traitement parallèle** : 10x plus rapide avec asyncio.gather
- **Optimisation vision** : Cooldown dynamique et priorisation des caméras

## 3.1.0
- **Webhooks HA** : Connexion WebSocket pour une réactivité temps réel
- **Retry exponentiel** : Avec jitter pour éviter la synchronisation
- **Fallback automatique** : Bascule en mode polling si échec

# Changelog

## 3.0.3
- Gemini : les erreurs 429 journalisent maintenant le détail donné par Google (quota dépassé, délai conseillé).
- Vision : la pause après un échec suit ce que dit Google (délai conseillé ; 60 min si le quota JOURNALIER est épuisé) ; le journal indique la cause.
- Vision : option `vision_model` pour utiliser un modèle plus léger (quota souvent plus large) sans changer celui de Jarvis.

## 3.0.2
- Vision : `vision_api_key` (optionnelle) donne à la vision sa propre clé Gemini, donc son propre quota : elle n'affame plus les réponses de Jarvis.
- Vision : un seul essai par image (plus de réessais sur un 429, qui aggravaient la saturation) et pause de 10 min après un échec.
- Vision : une analyse qui échoue ne consomme plus le budget quotidien.

## 3.0.1
- Voix : `speak_service: chime_tts.say` appelle Chime TTS directement (plateforme, langue et voix explicites : `speak_tts_platform`, `speak_language`, `speak_voice`), sans passer par un profil `notify.*`. Corrige le cas « Unsupported options: tld ».

## 3.0.0
- Ingénieur HA : propositions de création/modification/suppression d'automations et scripts, validation stricte, vérification, retour arrière automatique, annulation.
- Nettoyage d'entités fantômes (refus si référencées), `GET /api/hygiene`.
- Vision Frigate -> Gemini avec budget quotidien, délai par caméra, reconnaissance Frigate gratuite.
- Rôles (admin / member / guest), validation vocale par code avec blocage, mémoire par personne.
- Tout est désactivé par défaut ; 54 tests automatisés.

## 2.0.1
- Correctif : la règle `system_high` ne regarde plus que disque et mémoire (le CPU des conteneurs dépasse 100 % normalement : faux positif).

## 2.0.0
- Moteur d'autonomie : surveillance périodique, gravité urgent / important / minor.
- Propositions d'actions à valider (HUD), contrôle de l'approbateur, vérification d'état avant exécution, expiration.
- Journal SQLite persistant, alertes en cours conservées après redémarrage.
- Rapport vocal quotidien (`daily_report_time`), heures calmes, notification mobile (`notify_service`).
- Panneau « Autonomie » dans le HUD.
- Désactivé par défaut (`autonomy_enabled: false`) : aucune action nouvelle tant que tu ne l'actives pas.

## 1.7.0
- Présence directe du radar ESPHome (Apollo MTR-1).
