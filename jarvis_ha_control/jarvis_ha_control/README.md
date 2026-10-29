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
