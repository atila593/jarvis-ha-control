# Changelog

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
