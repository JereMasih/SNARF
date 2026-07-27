from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from snarf.capabilities.base import Capability

# google_client_secret.json identifica a la aplicación Snarf ante Google (un
# solo archivo, compartido por todos los usuarios que algún día usen Snarf).
# Cada usuario tiene, en cambio, su propio token de acceso en tokens/<user_id>.json.
CLIENT_SECRET_PATH = Path("credentials/google_client_secret.json")
TOKENS_DIR = Path("credentials/tokens")

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/youtube.readonly",
]


class GoogleAuth(Capability):
    name = "google_auth"

    def __init__(self, user_id: str):
        self._user_id = user_id
        self._creds = None

    @property
    def _token_path(self) -> Path:
        return TOKENS_DIR / f"{self._user_id}.json"

    @property
    def available(self) -> bool:
        return CLIENT_SECRET_PATH.exists()

    def credentials(self) -> Credentials:
        if self._creds and self._creds.valid:
            return self._creds

        token_path = self._token_path
        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.available:
                    raise RuntimeError(
                        f"Falta {CLIENT_SECRET_PATH}. Descargá las credenciales OAuth desde Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
                creds = flow.run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")

        self._creds = creds
        return creds
