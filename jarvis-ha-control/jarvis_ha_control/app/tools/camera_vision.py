import os
import requests
import google.generativeai as genai
from PIL import Image
from io import BytesIO

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SUPERVISOR_TOKEN = os.getenv("SUPERVISOR_TOKEN", "")
HA_URL = "http://supervisor/core/api"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def analyze_camera_snapshot(camera_entity: str, prompt: str = "Décris brièvement ce que tu vois : personne, véhicule, colis, ou situation suspecte.") -> str:
    """Récupère l'image instantanée d'une caméra HA et l'analyse via Gemini Vision."""
    if not GEMINI_API_KEY:
        return "Clé API Gemini non configurée."

    headers = {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }
    
    url = f"{HA_URL}/camera_proxy/{camera_entity}"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return f"Impossible de récupérer l'image de la caméra {camera_entity} (code {response.status_code})."
        
        image = Image.open(BytesIO(response.content))
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        full_prompt = f"Tu es Jarvis. Réponds de façon concise et naturelle en 2 phrases maximum pour la synthèse vocale : {prompt}"
        res = model.generate_content([full_prompt, image])
        return res.text.strip()
        
    except Exception as e:
        return f"Erreur lors de l'analyse vision : {str(e)}"
