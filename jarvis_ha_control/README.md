# Jarvis HA Control

Assistant Gemini pour Home Assistant, avec HUD web (panneau latéral "Jarvis" via Ingress).

## Ce que ça fait
- Répond à tes questions en connaissant l'état des lumières, volets, aspirateur, caméras, lecteurs et capteurs.
- Diagnostic du Core via l'API Supervisor.
- Optionnel : fait parler la réponse sur tes Echo via n'importe quel service `notify.*`.

## Tableau de bord
- Colonne gauche : aspirateur, serrures, capteurs de puissance (Linky), capteurs « problème ». Colonne droite : caméras et capteurs de connectivité. Détection automatique, rafraîchie toutes les 20 s.
- **Auto-Diagnostic** : état global, anomalies et analyse de Jarvis (si la clé Gemini est configurée).
- Téléchargements : rapport HTML (imprimable en PDF), TXT, JSON, et visuel PNG à envoyer.

## Présence (radar ESPHome, ex. Apollo MTR-1)
Jarvis lit directement les zones du radar (HLK-LD2450) : `sensor.<prefix>_zone_<n>_all_target_count`, sans intermédiaire. Détection automatique ; les zones non dessinées sur le radar (rectangle vide) et `Zone Type = Disabled` sont ignorées. Panneau « Présence » dans le HUD (rafraîchi toutes les 3 s), bloc dédié dans le contexte de Gemini (« qui est dans le salon ? »), et une phrase dans le rapport vocal. Le radar ne couvre que ses zones : Jarvis ne conclut jamais « personne dans l'appartement ». `hidden_entities` permet d'en masquer une.
Réglages : `presence_zone_names` (noms dans l'ordre des zones 1, 2, 3, ex. `salon`, `salle a manger`) et `presence_prefix` (ex. `apollo_mtr_1_5444e4`, utile seulement avec plusieurs radars).

## Rapport vocal (Alexa)
`POST /api/rapport` lance le diagnostic et le fait dire sur les enceintes (`speak_service` + `speak_targets`). Depuis Home Assistant : `rest_command` vers `http://<hostname-addon>:8099/api/rapport`, appelé par un script exposé à Alexa, puis une routine Alexa avec une phrase personnalisée.

## Scripts et automatisations
Jarvis peut lancer les scripts et déclencher les automatisations listés dans `action_entities` (et uniquement ceux-là).

## Contrôle de la maison
Jarvis peut agir quand tu le demandes clairement (« allume la salle à manger », « ferme le volet du salon »). Garde-fous : liste blanche de domaines (`allowed_domains`, par défaut lumières, volets, aspirateur, scènes), jamais de serrures ni d'alarme, jamais de `toggle`, entités masquées refusées, chaque action est écrite dans le journal. `actions_enabled: false` repasse en lecture seule.

## Ce que ça ne fait pas (encore)
- Aucune réparation automatique.

## Options
| Option | Rôle |
|---|---|
| `gemini_api_key` | Clé API Google AI Studio |
| `gemini_model` | ID du modèle (défaut `gemini-3.6-flash`) |
| `speak_service` | Service HA, ex. `notify.alexa_media` ou `notify.jarvis` (profil Chime TTS) |
| `speak_targets` | Cibles, ex. `media_player.echo_show_olivier` |
| `auto_speak` | Parle automatiquement chaque réponse |
| `gemini_fallback_model` | Modèle de secours si le principal est saturé |
| `actions_enabled` | Autorise Jarvis à agir (défaut : oui) |
| `allowed_domains` | Domaines pilotables (défaut : light, cover, vacuum, scene ; aussi switch, fan) |
| `action_entities` | Scripts/automatisations que Jarvis a le droit de lancer (ex. `script.alarme_garage`) |
| `auto_discover` | `true` : détecte aussi caméras, aspirateur, capteurs ; `false` : surveille uniquement `extra_entities` |
| `extra_entities` | Liste des entités à surveiller (classées automatiquement : modules, caméras/réseau, serveur/services) |
| `hidden_entities` | Entités à masquer du tableau |
| `presence_zone_names` | Noms des zones du radar, dans l'ordre (zone 1, zone 2...) ; sinon « Zone 1 »... |
| `presence_prefix` | Préfixe des entités du radar, seulement si plusieurs radars |

## v2.0 — Autonomie (phase 1)

Jarvis surveille la maison tout seul (lecture des états toutes les `autonomy_interval` secondes) et décide selon la gravité :

| Gravité | Exemples | Comportement |
|---|---|---|
| **urgent** | fumée, gaz, CO, fuite d'eau | parle (même la nuit) + notifie, rappel toutes les 10 min (3 max). N'agit seul que si la règle est dans `auto_rules` |
| **important** | porte de garage ouverte la nuit ou > 60 min, aspirateur en erreur, disque/mémoire > 95 %, CPU > 85 °C, vigilance météo rouge/orange | crée une **proposition** à valider dans le HUD, notifie, parle sauf la nuit |
| **minor** | entité surveillée indisponible > 30 min | noté dans le journal, repris dans le rapport du matin |

Règles disponibles (`autonomy_rules`, vide = toutes) : `safety_sensor`, `garage_open`, `vacuum_error`, `system_high`, `weather_alert`, `watched_unavailable`.

### Garde-fous
- **Rien n'est exécuté sans validation**, sauf règle listée dans `auto_rules` (vide par défaut).
- Les actions passent par la même liste blanche que les commandes : jamais de serrure ni d'alarme, jamais de `toggle`.
- À la validation, Jarvis **revérifie l'état** : si la situation a changé (porte déjà refermée), la proposition devient « obsolète » et rien n'est exécuté.
- `approvers` : seuls ces utilisateurs HA peuvent valider. L'identité vient des en-têtes Ingress et n'est acceptée que si la requête vient du proxy Ingress (`172.30.32.2`).
- Les propositions expirent après `proposal_ttl_minutes`.
- Tout est écrit dans le journal (`/data/jarvis.db`, panneau « Autonomie » du HUD, `GET /api/journal`).
- Les alertes en cours survivent à un redémarrage : pas de ré-annonce.

### Options ajoutées
`autonomy_enabled` (false par défaut), `autonomy_interval`, `autonomy_rules`, `auto_rules`, `approvers`, `quiet_start` / `quiet_end` (23:00 → 07:00), `notify_service` (ex. `notify.mobile_app_honor_v2`), `proposal_ttl_minutes`, `daily_report_time` (ex. `08:00`, vide = désactivé), `unavailable_minutes`.

### API
`GET /api/autonomy` · `GET /api/proposals?status=pending|all` · `POST /api/proposals/{id}/approve|reject` · `GET /api/journal?limit=`

### Limites connues
- La détection est par lecture périodique : latence maximale = `autonomy_interval` (30 s par défaut).
- Pas encore de voix d'entrée, de reconnaissance du locuteur, ni de vision caméra : ce sont les phases suivantes.
