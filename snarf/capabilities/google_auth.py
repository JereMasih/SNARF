from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from snarf.capabilities.base import Capability

# google_client_secret.json identifica a la aplicación Snarf ante Google (un
# solo archivo, compartido por todos los usuarios que algún día usen Snarf).
# Cada usuario tiene, en cambio, su propio token de acceso en tokens/<user_id>.json.
#
# IMPORTANTE (Fase 3 del plan de multi-usuario, ADR 0137): este archivo tiene
# que ser un cliente OAuth tipo "Web application" en Google Cloud Console
# (Credenciales → Crear credenciales → ID de cliente de OAuth → Aplicación
# web), con el/los "URI de redireccionamiento autorizados" reales dados de
# alta (ej. https://<dominio-o-tailscale>/google/oauth/callback) — el
# cliente tipo "Desktop app" que usaba el InstalledAppFlow original (ver
# ADR 0013, versión pre-Fase-3 de este archivo) NO funciona con el flujo
# real de abajo, que necesita un redirect_uri de verdad. Este paso de
# Google Cloud Console es una acción manual real que el fundador tiene que
# hacer — ningún cambio de código puede reemplazarlo.
CLIENT_SECRET_PATH = Path("credentials/google_client_secret.json")
TOKENS_DIR = Path("credentials/tokens")

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/youtube.readonly",
]

# Scopes de identidad (Fase 3, ADR 0137) — se piden junto con los de arriba
# en el mismo consentimiento cuando este flujo se usa también para "Sign in
# with Google" (ver snarf/runtime/google_identity.py y GET /login/google en
# app.py): un usuario nuevo conecta su cuenta de Google UNA sola vez, y de
# ahí sale tanto su acceso real (Drive/Gmail/Calendar/YouTube) como su
# identidad real (email) — sin un segundo login aparte.
IDENTITY_SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email"]

ALL_SCOPES = SCOPES + IDENTITY_SCOPES


def token_path(user_id: str) -> Path:
    return TOKENS_DIR / f"{user_id}.json"


def client_secret_available() -> bool:
    return CLIENT_SECRET_PATH.exists()


def build_authorization_url(redirect_uri: str, state: str) -> str:
    """Arma la URL real de consentimiento de Google (Fase 3 del plan de
    multi-usuario, ADR 0137) — reemplaza el InstalledAppFlow.
    run_local_server() de antes, que abría un navegador y un servidor HTTP
    LOCAL en la máquina que corre Snarf: funcionaba solo para el fundador
    operando esa Mac directo, nunca para un usuario remoto real conectando
    su propia cuenta desde su propio navegador. `state` viaja generado y
    firmado desde afuera (ver app.py) — protección CSRF real, nunca un
    valor inventado acá."""
    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRET_PATH), scopes=ALL_SCOPES, redirect_uri=redirect_uri, state=state
    )
    authorization_url, _ = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    return authorization_url


def exchange_code(redirect_uri: str, state: str, authorization_response: str) -> Credentials:
    """Intercambia el código real que Google mandó al callback por
    credenciales reales — el intercambio (fetch_token) es contra la API real
    de Google, nunca simulado del lado de Snarf."""
    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRET_PATH), scopes=ALL_SCOPES, redirect_uri=redirect_uri, state=state
    )
    flow.fetch_token(authorization_response=authorization_response)
    return flow.credentials


def save_token(user_id: str, creds: Credentials) -> None:
    path = token_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(creds.to_json(), encoding="utf-8")


class GoogleAuth(Capability):
    name = "google_auth"

    def __init__(self, user_id: str):
        self._user_id = user_id
        self._creds = None

    @property
    def _token_path(self) -> Path:
        return token_path(self._user_id)

    @property
    def available(self) -> bool:
        return CLIENT_SECRET_PATH.exists()

    @property
    def connected(self) -> bool:
        return self._token_path.exists()

    def credentials(self) -> Credentials:
        if self._creds and self._creds.valid:
            return self._creds

        stored_path = self._token_path
        creds = None
        if stored_path.exists():
            creds = Credentials.from_authorized_user_file(str(stored_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Antes no se re-guardaba tras un refresh (bug real, menor:
                # el access_token fresco se perdía en cada reinicio del
                # proceso, forzando un refresh de más contra Google la
                # próxima vez) — se persiste acá para no repetirlo.
                stored_path.write_text(creds.to_json(), encoding="utf-8")
            else:
                # Fase 3 (ADR 0137): ya no dispara un flujo interactivo acá
                # adentro. InstalledAppFlow.run_local_server() abría un
                # navegador + un server HTTP local en la máquina de Snarf —
                # nunca funcionó para un usuario remoto real, solo para
                # quien tuviera acceso directo a esa Mac. Conectar Google es
                # ahora un paso explícito del usuario vía GET /google/connect
                # (ver app.py), que sí redirige al propio navegador del
                # usuario.
                raise RuntimeError(
                    "Google no está conectado para este usuario — conectalo desde la interfaz "
                    "(Configuración → Conectar Google) antes de usar esta capacidad."
                )

        self._creds = creds
        return creds
