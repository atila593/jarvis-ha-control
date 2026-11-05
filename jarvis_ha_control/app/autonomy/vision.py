"""Vision : Jarvis regarde les événements Frigate et décide s'ils méritent une réaction.

Économie du quota Gemini gratuit :
  - une personne déjà reconnue par Frigate (sub_label) n'envoie AUCUNE image à Gemini ;
  - délai minimum entre deux analyses d'une même caméra ;
  - budget quotidien d'images (`vision_daily_budget`), au-delà : simple note dans le journal.

Vie privée : l'IA décrit la scène, elle ne cherche jamais à identifier quelqu'un par son visage.
"""
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

from autonomy.rules import Finding, in_window

logger = logging.getLogger("JarvisVision")

PROMPT = (
    "Tu analyses l'image d'une caméra de surveillance d'une maison. Caméra : {camera}. Objet détecté : {label}. "
    "Heure locale : {time}. Décris la scène sans jamais chercher à identifier une personne par son visage. "
    "Réponds UNIQUEMENT par un JSON : "
    '{{"who": "habitant|livreur|inconnu|animal|vehicule|autre", "threat": 0, "summary": "une phrase courte en français"}}. '
    "threat : 0 = normal (livreur, facteur, passant, animal, voiture qui passe), "
    "1 = à vérifier (inconnu qui s'attarde, regarde les fenêtres ou essaie une porte), "
    "2 = intrusion ou comportement agressif."
)


@dataclass
class VisionSettings:
    enabled: bool = False
    frigate_url: str = ""
    labels: list = field(default_factory=lambda: ["person"])
    cameras: list = field(default_factory=list)      # vide = toutes
    daily_budget: int = 60
    cooldown_min: int = 5


def parse_verdict(text: str) -> dict:
    """Tolère les blocs ```json et le texte autour ; sinon repli prudent (à vérifier)."""
    raw = (text or "").strip()
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
        threat = int(data.get("threat", 1))
        return {"who": str(data.get("who") or "autre").lower(), "threat": max(0, min(2, threat)),
                "summary": str(data.get("summary") or "").strip()[:240] or "Scène à vérifier."}
    except Exception:
        return {"who": "autre", "threat": 1, "summary": (raw[:200] or "Analyse illisible, à vérifier.")}


def severity_for(verdict: dict, night: bool) -> str:
    threat = verdict["threat"]
    if threat >= 2:
        return "urgent" if night else "important"          # une IA qui crie à l'intrusion : urgence seulement la nuit
    if threat == 1 or (night and verdict["who"] in ("inconnu", "autre")):
        return "important"
    return "minor"


class Vision:
    def __init__(self, store, settings: VisionSettings, quiet_start, quiet_end, *, get_json, get_bytes, describe):
        self.store = store
        self.s = settings
        self.quiet = (quiet_start, quiet_end)
        self.get_json = get_json        # async (url, params) -> list[dict]
        self.get_bytes = get_bytes      # async (url) -> bytes | None
        self.describe = describe        # async (image_bytes, prompt) -> str
        self._last_cam: dict = {}
        self._down = False
        self._budget_logged = None

    def _budget_key(self, now: datetime) -> str:
        return f"vision_n_{now.date().isoformat()}"

    def used_today(self, now: datetime) -> int:
        return int(self.store.meta_get(self._budget_key(now)) or 0)

    async def poll(self, now: datetime) -> list:
        if not (self.s.enabled and self.s.frigate_url):
            return []
        base = self.s.frigate_url.rstrip("/")
        after = float(self.store.meta_get("vision_last_ts") or (now.timestamp() - 300))
        try:
            events = await self.get_json(f"{base}/api/events", {"after": after, "limit": 30, "has_snapshot": 1})
            if self._down:
                self.store.log("info", "vision", "Frigate de nouveau joignable.")
                self._down = False
        except Exception as e:
            if not self._down:
                self.store.log("minor", "vision", f"Frigate injoignable : {e}")
                self._down = True
            return []

        findings = []
        night = in_window(now.time(), *self.quiet)
        for ev in sorted(events, key=lambda x: x.get("start_time", 0)):
            ts = float(ev.get("start_time", 0))
            if ts <= after:
                continue
            self.store.meta_set("vision_last_ts", str(ts))
            cam, label = ev.get("camera", "?"), ev.get("label", "")
            if self.s.labels and label not in self.s.labels:
                continue
            if self.s.cameras and cam not in self.s.cameras:
                continue

            sub = ev.get("sub_label")
            sub = sub[0] if isinstance(sub, (list, tuple)) and sub else sub
            if sub:                                                     # personne déjà reconnue par Frigate : gratuit
                findings.append(Finding("vision", f"camera.{cam}", "minor", f"{sub} a été vue à la caméra {cam}."))
                continue

            if ts - self._last_cam.get(cam, 0) < self.s.cooldown_min * 60:
                continue
            if self.used_today(now) >= self.s.daily_budget:
                if self._budget_logged != now.date():
                    self.store.log("minor", "vision", f"Budget d'images atteint ({self.s.daily_budget}/jour) : analyses suspendues.")
                    self._budget_logged = now.date()
                continue
            try:
                img = await self.get_bytes(f"{base}/api/events/{ev['id']}/snapshot.jpg")
                if not img:
                    continue
                self._last_cam[cam] = ts
                self.store.meta_set(self._budget_key(now), str(self.used_today(now) + 1))
                text = await self.describe(img, PROMPT.format(camera=cam, label=label, time=now.strftime("%H:%M")))
            except Exception as e:
                logger.warning("Analyse impossible (%s) : %s", ev.get("id"), e)
                self.store.log("minor", "vision", f"Analyse impossible pour la caméra {cam} : {e}")
                continue
            verdict = parse_verdict(text)
            findings.append(Finding("vision", f"camera.{cam}", severity_for(verdict, night),
                                    f"Caméra {cam} : {verdict['summary']}"))
        return findings
