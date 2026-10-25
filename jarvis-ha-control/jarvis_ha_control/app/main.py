import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from assistant.gemini_engine import GeminiUnavailable, JarvisEngine  # noqa: E402
from tools import status as st  # noqa: E402
from tools.speak import speak  # noqa: E402
from tools.sys_diagnose import SystemDiagnose  # noqa: E402

logging.basicConfig(level=config.LOG_LEVEL)
logger = logging.getLogger("JarvisCore")

app = FastAPI(title="Jarvis HA Control", version="1.3.0")
jarvis = JarvisEngine()
diagnose = SystemDiagnose()


class CommandRequest(BaseModel):
    prompt: str
    speak: bool | None = None


class SpeakRequest(BaseModel):
    text: str


@app.post("/api/command")
async def handle_command(req: CommandRequest):
    try:
        response, actions = await jarvis.process_command(req.prompt)
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


@app.post("/api/diagnostic")
async def run_diagnostic(req: DiagRequest):
    status = await st.build_status(diagnose)
    analysis = None
    if req.analyse:
        try:
            analysis = await jarvis.analyse(st.render_txt(st.build_report(status, None)))
        except GeminiUnavailable as e:
            analysis = f"Analyse IA indisponible : {e}"
        except Exception as e:
            logger.exception("Analyse impossible")
            analysis = f"Analyse IA indisponible : {e}"
    report = st.build_report(status, analysis)
    LAST["report"] = report
    spoken = await speak(analysis) if (req.speak and analysis) else {"spoken": False}
    return {"status": "success", "report": report, "speech": spoken}


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


webui = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webui")
if os.path.isdir(webui):
    app.mount("/", StaticFiles(directory=webui, html=True), name="webui")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8099, log_level=config.LOG_LEVEL.lower())
