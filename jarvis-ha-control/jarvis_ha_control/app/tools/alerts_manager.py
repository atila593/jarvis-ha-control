import json
import os
from datetime import datetime

ALERTS_FILE = "/data/jarvis_alerts.json"

def save_alerts_summary(anomalies: list, overall_status: str) -> str:
    """Filtre les vraies alertes et prépare un résumé concis pour les enceintes Echo."""
    critical_anomalies = []
    for item in anomalies:
        entity = item.get("entity_id", "")
        # On ignore Android Auto s'il est simplement déconnecté (état off normal)
        if "android_auto" in entity and item.get("state") == "off":
            continue
        critical_anomalies.append(item.get("name", entity))

    now_str = datetime.now().strftime("%H:%M")
    
    if not critical_anomalies:
        speech_text = f"Tout est en ordre à {now_str}. Aucun problème critique détecté."
    else:
        count = len(critical_anomalies)
        details = ", ".join(critical_anomalies[:3])
        speech_text = f"À {now_str}, j'ai relevé {count} point(s) d'attention : {details}."

    data = {
        "timestamp": datetime.now().isoformat(),
        "status": overall_status,
        "speech_text": speech_text,
        "anomalies_count": len(critical_anomalies),
        "anomalies": critical_anomalies
    }

    try:
        with open(ALERTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return speech_text

def get_latest_speech_summary() -> str:
    """Récupère le dernier résumé vocal enregistré."""
    if not os.path.exists(ALERTS_FILE):
        return "Aucun rapport récent n'est disponible pour le moment."
    try:
        with open(ALERTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("speech_text", "Rapport indisponible.")
    except Exception:
        return "Erreur lors de la lecture des alertes."
