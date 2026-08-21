import base64
import json
import os
from pathlib import Path
from urllib.parse import urlencode

import requests

from snarf.capabilities.base import Capability

# Requiere que la integración de Snarf esté registrada como PÚBLICA en el
# panel de developers de Notion (https://www.notion.so/my-integrations) —
# a diferencia del token fijo de "internal integration" que usa hoy
# NOTION_API_KEY (snarf/capabilities/notion.py, un solo token para todo el
# workspace del fundador), una integración pública tiene su propio
# client_id/client_secret y puede autorizar a CUALQUIER usuario de Notion
# que la instale, no solo al fundador. Paso manual real del fundador en el
# panel de Notion — ningún cambio de código puede reemplazarlo (ver ADR
# 0186, mismo tipo de gotcha ya documentado en CLAUDE.md para Google Cloud
# Console/TCC de macOS).
NOTION_OAUTH_AUTHORIZE_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_OAUTH_TOKEN_URL = "https://api.notion.com/v1/oauth/token"

TOKENS_DIR = Path("credentials/notion_tokens")


def token_path(user_id: str) -> Path:
    return TOKENS_DIR / f"{user_id}.json"


def client_credentials_available() -> bool:
    return bool(os.environ.get("NOTION_OAUTH_CLIENT_ID")) and bool(os.environ.get("NOTION_OAUTH_CLIENT_SECRET"))


def build_authorization_url(redirect_uri: str, state: str) -> str:
    """Arma la URL real de consentimiento de Notion — a diferencia de
    Google, Notion no tiene un SDK propio de OAuth para Python, así que
    esto arma la URL a mano siguiendo la doc real de la API
    (`owner=user`: la integración pide autorización sobre el workspace real
    que el usuario elija en la pantalla de Notion, nunca asumido de
    antemano)."""
    client_id = os.environ["NOTION_OAUTH_CLIENT_ID"]
    params = {
        "client_id": client_id,
        "response_type": "code",
        "owner": "user",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{NOTION_OAUTH_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(redirect_uri: str, code: str) -> dict:
    """Intercambia el código real que Notion mandó al callback por un token
    de acceso real — POST directo con Basic Auth (client_id:client_secret),
    siguiendo la doc real de la API de Notion (sin SDK propio para esto en
    Python). A diferencia de Google, la respuesta de Notion no incluye
    expiración ni refresh_token — el access_token no expira (documentado
    así por Notion), por eso NotionAuth más abajo no tiene ningún mecanismo
    de refresh."""
    client_id = os.environ["NOTION_OAUTH_CLIENT_ID"]
    client_secret = os.environ["NOTION_OAUTH_CLIENT_SECRET"]
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    response = requests.post(
        NOTION_OAUTH_TOKEN_URL,
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/json"},
        json={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def save_token(user_id: str, token_data: dict) -> None:
    path = token_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(token_data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_token(user_id: str) -> dict | None:
    path = token_path(user_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


class NotionAuth(Capability):
    name = "notion_auth"

    def __init__(self, user_id: str):
        self._user_id = user_id

    @property
    def available(self) -> bool:
        return client_credentials_available()

    @property
    def connected(self) -> bool:
        return token_path(self._user_id).exists()

    def access_token(self) -> str | None:
        """Token real de este usuario si ya conectó su Notion vía OAuth —
        None si nunca lo conectó (quien use esto, ver Notion._resolve_token,
        cae de vuelta al NOTION_API_KEY global en ese caso)."""
        token_data = load_token(self._user_id)
        return token_data.get("access_token") if token_data else None

    def workspace_name(self) -> str | None:
        token_data = load_token(self._user_id)
        return token_data.get("workspace_name") if token_data else None
