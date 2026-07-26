from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from snarf.capabilities.base import Capability

CLIENT_SECRET_PATH = Path("credentials/google_client_secret.json")
TOKEN_PATH = Path("credentials/google_token.json")

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/youtube.readonly",
]


class GoogleAuth(Capability):
    name = "google_auth"

    def __init__(self):
        self._creds = None

    @property
    def available(self) -> bool:
        return CLIENT_SECRET_PATH.exists()

    def credentials(self) -> Credentials:
        if self._creds and self._creds.valid:
            return self._creds

        creds = None
        if TOKEN_PATH.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

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
            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

        self._creds = creds
        return creds
