import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # noqa: E402
from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from assistant.gemini_engine import GeminiUnavailable, JarvisEngine  # noqa: E402
from autonomy import access  # noqa: E402
from autonomy import rules as arules  # noqa: E402
from autonomy.engine import AutonomyEngine, Settings  # noqa: E402
from autonomy.engineer import Engineer  # noqa: E402
from autonomy.ha import HaClient  # noqa: E402
from autonomy.store import Store  # noqa: E402
from autonomy.vision import Vision, VisionSettings  # noqa: E402
from tools.toolbox import Toolbox  # noqa: E402
from tools import presence  # noqa: E402
from tools.actions import ActionRunner  # noqa: E402
from tools import status as st  # noqa: E402
from tools.speak import speak  # noqa: E402
from tools.sys_diagnose import SystemDiagnose  # noqa: E402

logging.basicConfig(level=config.LOG_LEVEL)
logger = logging.getLogger("JarvisCore")

VERSION = "3.0.2"
INGRESS_IP = "172.30.32.2"  # seul le proxy Ingress du Supervisor peut valider une proposition
jarvis = JarvisEngine()
diagnose = SystemDiagnose()
autonomy: AutonomyEngine | None = None
engineer: Engineer | None = None
gate: access.VoiceGate | None = None
ROLES: dict = {}
_TZ = {"name": None}


async def _local_now() -> datetime:
    if not _TZ["name"]:
        try:
            _TZ["name"] = (await st._ha_get("config")).get("time_zone") or "UTC"
        except Exception:
            return datetime.now(ZoneInfo("UTC"))
    return datetime.now(ZoneInfo(_TZ["name"]))


async def _notify(title: str, message: str) -> None:
    service = config.NOTIFY_SERVICE
    if not service or "." not in service:
        return
    domain, name = service.split(".", 1)
    headers = {"Authorization": f"Bearer {config.SUPERVISOR_TOKEN}"}
    import httpx
    async with httpx.AsyncClient(timeout=10) as http:
        res = await http.post(f"{config.HA_API_URL}/services/{domain}/{name}", headers=headers,
                              json={"title": title, "message": message})
    res.raise_for_status()


async def _execute(domain: str, service: str, entity_id: str) -> str:
    """Passe par la même liste blanche que les commandes vocales/texte."""
    return await ActionRunner({entity_id}).call_service(domain, service, entity_id)


async def _speak_text(text: str) -> None:
    await speak(text)


async def _spoken_report() -> str:
    return st.spoken_summary(await _make_report(True))


def build_autonomy() -> AutonomyEngine:
    params = arules.Params(
        quiet_start=arules.parse_time(config.QUIET_START, arules.time(23, 0)),
        quiet_end=arules.parse_time(config.QUIET_END, arules.time(7, 0)),
        unavailable_min=config.UNAVAILABLE_MIN,
        watched=list(config.EXTRA_ENTITIES),
        hidden=list(config.HIDDEN_ENTITIES),
        enabled=list(config.AUTONOMY_RULES),
    )
    settings = Settings(
        enabled=config.AUTONOMY_ENABLED, interval=config.AUTONOMY_INTERVAL, auto_rules=list(config.AUTO_RULES),
        approvers=list(config.APPROVERS), proposal_ttl_min=config.PROPOSAL_TTL_MIN,
        daily_report_time=config.DAILY_REPORT_TIME,
    )
    store = Store()
    ha = HaClient(config.HA_API_URL, config.HA_WS_URL, config.SUPERVISOR_TOKEN)
    global engineer, gate, ROLES
    engineer = Engineer(store, ha, edit_existing=config.ENGINEER_EDIT_EXISTING)
    ROLES = access.parse_roles(config.USER_ROLES)

    async def get_json(url, params):
        import httpx
        async with httpx.AsyncClient(timeout=10) as http:
            res = await http.get(url, params=params)
        res.raise_for_status()
        return res.json()

    async def get_bytes(url):
        import httpx
        async with httpx.AsyncClient(timeout=15) as http:
            res = await http.get(url)
        return res.content if res.status_code == 200 else None

    vision = Vision(
        store,
        VisionSettings(enabled=config.VISION_ENABLED, frigate_url=config.FRIGATE_URL, labels=list(config.VISION_LABELS),
                       cameras=list(config.VISION_CAMERAS), daily_budget=config.VISION_DAILY_BUDGET,
                       cooldown_min=config.VISION_COOLDOWN_MIN),
        params.quiet_start, params.quiet_end,
        get_json=get_json, get_bytes=get_bytes, describe=jarvis.describe_image,
    ) if config.VISION_ENABLED else None

    engine = AutonomyEngine(
        store, settings, params,
        fetch_states=lambda: st._ha_get("states"), execute=_execute, speak=_speak_text,
        notify=_notify, report=_spoken_report, local_now=_local_now,
        handlers={"config_change": engineer.apply_change, "entity_remove": engineer.remove_entity},
        vision=vision,
    )
    gate = access.VoiceGate(engine, engineer, config.VOICE_PIN, config.VOICE_ENABLED)
    return engine


@asynccontextmanager
async def lifespan(_app):
    global autonomy
    autonomy = build_autonomy()
    task = asyncio.create_task(autonomy.run()) if config.AUTONOMY_ENABLED else None
    logger.info("Jarvis %s démarré — autonomie %s", VERSION, "ACTIVE" if task else "désactivée")
    yield
    if task:
        task.cancel()


app = FastAPI(title="Jarvis HA Control", version=VERSION, lifespan=lifespan)


class CommandRequest(BaseModel):
    prompt: str
    speak: bool | None = None
    who: str | None = None


class SpeakRequest(BaseModel):
    text: str


def _trusted(request: Request) -> bool:
    return os.getenv("JARVIS_DEV") == "1" or bool(request.client and request.client.host == INGRESS_IP)


def _identity(request: Request, body_who: str | None = None) -> tuple[str | None, str]:
    """(qui, rôle). Via le panneau Jarvis (Ingress, réservé aux admins HA) : admin par défaut.
    Appel extérieur (automation, satellite) : le rôle vient de `user_roles`, inconnu = lecture seule."""
    header = request.headers.get("X-Remote-User-Display-Name") or request.headers.get("X-Remote-User-Name")
    if _trusted(request) and not body_who:
        return header, access.role_of(header, ROLES, default="admin")
    return body_who, access.role_of(body_who, ROLES, default="guest")


def _toolbox(who, role):
    return Toolbox(engineer, autonomy.store, who, role, engineer_on=config.ENGINEER_ENABLED,
                   memory_on=config.MEMORY_ENABLED, stale_days=config.STALE_DAYS)


async def _ask_jarvis(prompt: str, who, role):
    facts = [f["fact"] for f in autonomy.store.facts(who)] if (config.MEMORY_ENABLED and who) else None
    return await jarvis.process_command(prompt, who=who, role=role, toolbox=_toolbox(who, role), facts=facts)


@app.post("/api/command")
async def handle_command(req: CommandRequest, request: Request):
    who, role = _identity(request, req.who)
    try:
        response, actions = await _ask_jarvis(req.prompt, who, role)
    except GeminiUnavailable as e:
        logger.error("%s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Erreur de traitement")
        raise HTTPException(status_code=500, detail=f"Erreur interne : {e}")
    do_speak = config.AUTO_SPEAK if req.speak is None else req.speak
    spoken = await speak(response) if do_speak else {"spoken": False}
    return {"status": "success", "response": response, "actions": actions, "speech": spoken}


@app.post("/api/speak")
async def handle_speak(req: SpeakRequest):
    return {"status": "success", "speech": await speak(req.text)}


class DiagRequest(BaseModel):
    analyse: bool = True
    speak: bool = False


LAST = {"report": None}


@app.get("/api/status")
async def get_status():
    return await st.build_status(diagnose)


@app.get("/api/presence")
async def get_presence():
    """Présence seule, légère : le HUD l'appelle toutes les 3 s."""
    return {"items": await presence.fast()}


async def _make_report(analyse: bool) -> dict:
    status = await st.build_status(diagnose)
    analysis = None
    if analyse:
        try:
            analysis = await jarvis.analyse(st.render_txt(st.build_report(status, None)))
        except GeminiUnavailable as e:
            analysis = f"Analyse IA indisponible : {e}"
        except Exception as e:
            logger.exception("Analyse impossible")
            analysis = f"Analyse IA indisponible : {e}"
    report = st.build_report(status, analysis)
    LAST["report"] = report
    return report


@app.post("/api/diagnostic")
async def run_diagnostic(req: DiagRequest):
    report = await _make_report(req.analyse)
    spoken = await speak(st.spoken_summary(report)) if req.speak else {"spoken": False}
    return {"status": "success", "report": report, "speech": spoken}


class RapportRequest(BaseModel):
    analyse: bool = True
    speak: bool = True


@app.post("/api/rapport")
async def run_rapport(req: RapportRequest):
    """Point d'entrée pour Alexa / Home Assistant : fait le diagnostic et le dit à voix haute."""
    report = await _make_report(req.analyse)
    text = st.spoken_summary(report)
    spoken = await speak(text) if req.speak else {"spoken": False}
    return {"status": "success", "text": text, "speech": spoken, "report": report}


@app.get("/api/report")
async def download_report(format: str = "html"):
    report = LAST["report"] or st.build_report(await st.build_status(diagnose), None)
    stamp = report["generated"].replace(" ", "-").replace(":", "")
    if format == "json":
        import json
        body, mime = json.dumps(report, ensure_ascii=False, indent=2), "application/json"
    elif format == "txt":
        body, mime = st.render_txt(report), "text/plain; charset=utf-8"
    else:
        format, body, mime = "html", st.render_html(report), "text/html; charset=utf-8"
    return Response(body, media_type=mime,
                    headers={"Content-Disposition": f'attachment; filename="jarvis-diagnostic-{stamp}.{format}"'})


@app.get("/api/diagnostics")
async def get_diagnostics():
    return {"status": "success", "data": await diagnose.check_system_health()}


def _approver(request: Request) -> str | None:
    """Identité de l'approbateur, lue dans les en-têtes Ingress (posés par le Supervisor).

    Si des `approvers` sont configurés, on exige que la requête vienne du proxy Ingress :
    sans cela un autre add-on pourrait forger l'en-tête.
    """
    names = [n for n in (request.headers.get("X-Remote-User-Name"),
                         request.headers.get("X-Remote-User-Display-Name")) if n]
    if autonomy and autonomy.s.approvers:
        trusted = os.getenv("JARVIS_DEV") == "1" or (request.client and request.client.host == INGRESS_IP)
        if not trusted:
            return None
    ok = next((n for n in names if autonomy and autonomy.authorised(n)), None)
    return ok or (names[0] if names else None)


@app.get("/api/autonomy")
async def get_autonomy():
    return autonomy.snapshot(await _local_now())


@app.get("/api/proposals")
async def get_proposals(status: str = "pending"):
    return {"items": autonomy.store.proposals(None if status == "all" else status)}


async def _decide(pid: int, approve: bool, request: Request):
    res = await autonomy.decide(pid, approve, _approver(request))
    if not res["ok"]:
        raise HTTPException(status_code=res["code"], detail=res["detail"])
    return res


@app.post("/api/proposals/{pid}/approve")
async def approve_proposal(pid: int, request: Request):
    return await _decide(pid, True, request)


@app.post("/api/proposals/{pid}/reject")
async def reject_proposal(pid: int, request: Request):
    return await _decide(pid, False, request)


@app.get("/api/journal")
async def get_journal(limit: int = 30):
    return {"items": autonomy.store.journal(min(max(limit, 1), 200))}


class VoiceRequest(BaseModel):
    text: str
    who: str | None = None


@app.post("/api/voice/ask")
async def voice_ask(req: VoiceRequest, request: Request):
    """Point d'entrée vocal (satellite / Assist) : valide par code, sinon répond comme une conversation normale."""
    who, role = _identity(request, req.who)
    handled = await gate.handle(req.text, who, role)
    if handled is not None:
        return {"status": "success", "response": handled, "handled": "voice_gate"}
    try:
        response, actions = await _ask_jarvis(req.text, who, role)
    except GeminiUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"status": "success", "response": response, "actions": actions, "handled": "chat"}


@app.get("/api/changes")
async def get_changes(limit: int = 20):
    return {"items": autonomy.store.changes(min(max(limit, 1), 100))}


@app.post("/api/changes/{cid}/undo")
async def undo_change(cid: int, request: Request):
    user = _approver(request)
    if not autonomy.authorised(user):
        raise HTTPException(status_code=403, detail="Seul un approbateur autorisé peut annuler.")
    result = await engineer.undo(cid)
    if result.startswith("ERREUR"):
        raise HTTPException(status_code=409, detail=result)
    return {"status": "success", "result": result}


@app.get("/api/hygiene")
async def get_hygiene():
    items = await engineer.stale_entities(config.STALE_DAYS, (await _local_now()).astimezone(ZoneInfo("UTC")))
    return {"count": len(items), "items": items[:200]}


@app.get("/api/memory")
async def get_memory(request: Request):
    if not _trusted(request):
        raise HTTPException(status_code=403, detail="Accès réservé au panneau Jarvis.")
    return {"items": autonomy.store.facts(None, 200)}


@app.delete("/api/memory/{fid}")
async def delete_memory(fid: int, request: Request):
    if not _trusted(request):
        raise HTTPException(status_code=403, detail="Accès réservé au panneau Jarvis.")
    if not autonomy.store.delete_fact(fid):
        raise HTTPException(status_code=404, detail="Fait introuvable.")
    return {"status": "success"}


webui = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webui")
if os.path.isdir(webui):
    app.mount("/", StaticFiles(directory=webui, html=True), name="webui")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8099, log_level=config.LOG_LEVEL.lower())
