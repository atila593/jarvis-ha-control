import json
import os

OPTIONS_PATH = os.getenv("OPTIONS_PATH", "/data/options.json")


def load_options() -> dict:
    try:
        with open(OPTIONS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


OPTIONS = load_options()

GEMINI_API_KEY = OPTIONS.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = OPTIONS.get("gemini_model") or "gemini-3.6-flash"
GEMINI_FALLBACK_MODEL = OPTIONS.get("gemini_fallback_model") or ""
LOG_LEVEL = (OPTIONS.get("log_level") or "info").upper()
SPEAK_SERVICE = (OPTIONS.get("speak_service") or "").strip()
SPEAK_TARGETS = OPTIONS.get("speak_targets") or []
ACTION_ENTITIES = OPTIONS.get("action_entities") or []
AUTO_DISCOVER = bool(OPTIONS.get("auto_discover", True))
EXTRA_ENTITIES = OPTIONS.get("extra_entities") or []
HIDDEN_ENTITIES = OPTIONS.get("hidden_entities") or []
PRESENCE_PREFIX = (OPTIONS.get("presence_prefix") or "").strip()
PRESENCE_ZONE_NAMES = [str(n) for n in (OPTIONS.get("presence_zone_names") or [])]
ACTIONS_ENABLED = bool(OPTIONS.get("actions_enabled", True))
ALLOWED_DOMAINS = OPTIONS.get("allowed_domains") or ["light", "cover", "vacuum", "scene"]
AUTO_SPEAK = bool(OPTIONS.get("auto_speak", False))

# --- Autonomie (v2) ---------------------------------------------------------
AUTONOMY_ENABLED = bool(OPTIONS.get("autonomy_enabled", False))
AUTONOMY_INTERVAL = int(OPTIONS.get("autonomy_interval") or 30)
AUTONOMY_RULES = OPTIONS.get("autonomy_rules") or []        # vide = toutes les règles
AUTO_RULES = OPTIONS.get("auto_rules") or []                # règles autorisées à agir seules (urgence)
APPROVERS = OPTIONS.get("approvers") or []                  # qui peut valider une proposition
QUIET_START = (OPTIONS.get("quiet_start") or "23:00").strip()
QUIET_END = (OPTIONS.get("quiet_end") or "07:00").strip()
NOTIFY_SERVICE = (OPTIONS.get("notify_service") or "").strip()
PROPOSAL_TTL_MIN = int(OPTIONS.get("proposal_ttl_minutes") or 120)
DAILY_REPORT_TIME = (OPTIONS.get("daily_report_time") or "").strip()
UNAVAILABLE_MIN = int(OPTIONS.get("unavailable_minutes") or 30)

SUPERVISOR_TOKEN = os.getenv("SUPERVISOR_TOKEN", "")
SUPERVISOR_URL = "http://supervisor"
HA_API_URL = os.getenv("HA_API_URL", "http://supervisor/core/api")

# --- v3 : ingénieur HA, vision, mémoire, voix ---------------------------------
ENGINEER_ENABLED = bool(OPTIONS.get("engineer_enabled", False))
ENGINEER_EDIT_EXISTING = bool(OPTIONS.get("engineer_edit_existing", False))
STALE_DAYS = int(OPTIONS.get("stale_days") or 7)
VISION_ENABLED = bool(OPTIONS.get("vision_enabled", False))
VISION_API_KEY = (OPTIONS.get("vision_api_key") or "").strip()   # vide = même clé que Jarvis
FRIGATE_URL = (OPTIONS.get("frigate_url") or "").strip()
VISION_LABELS = OPTIONS.get("vision_labels") or ["person"]
VISION_CAMERAS = OPTIONS.get("vision_cameras") or []
VISION_DAILY_BUDGET = int(OPTIONS.get("vision_daily_budget") or 60)
VISION_COOLDOWN_MIN = int(OPTIONS.get("vision_cooldown_minutes") or 5)
MEMORY_ENABLED = bool(OPTIONS.get("memory_enabled", False))
VOICE_ENABLED = bool(OPTIONS.get("voice_enabled", False))
VOICE_PIN = (OPTIONS.get("voice_pin") or "").strip()
USER_ROLES = OPTIONS.get("user_roles") or []                 # ex. "Olivier:admin", "Sarah:member"
HA_WS_URL = os.getenv("HA_WS_URL", "ws://supervisor/core/websocket")

# --- Voix : appel direct à chime_tts.say (speak_service: chime_tts.say) --------
SPEAK_TTS_PLATFORM = (OPTIONS.get("speak_tts_platform") or "tts.piper").strip()
SPEAK_LANGUAGE = (OPTIONS.get("speak_language") or "fr_FR").strip()
SPEAK_VOICE = (OPTIONS.get("speak_voice") or "fr_FR-tom-medium").strip()
