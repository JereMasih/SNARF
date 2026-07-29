import os
import secrets

from fastapi import Cookie, HTTPException, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

SESSION_COOKIE_NAME = "snarf_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 días
_SIGNING_SALT = "snarf-session"


def _serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt=_SIGNING_SALT)


def create_session_token(secret: str, user_id: str) -> str:
    return _serializer(secret).dumps({"user_id": user_id})


def verify_session_token(secret: str, token: str) -> str | None:
    try:
        data = _serializer(secret).loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("user_id")


def password_matches(candidate: str) -> bool:
    """Comparación a tiempo constante contra SNARF_ACCESS_PASSWORD, para no
    filtrar por temporización si la contraseña es correcta o no."""
    expected = os.environ.get("SNARF_ACCESS_PASSWORD")
    if not expected:
        return False
    # secrets.compare_digest no acepta str con caracteres no-ASCII (ej. tildes,
    # ñ) — codificar a bytes lo soporta sin perder la comparación a tiempo
    # constante.
    return secrets.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))


def require_user(snarf_session: str | None = Cookie(default=None)) -> str:
    """Dependencia de FastAPI: exige una cookie de sesión válida. Falla
    cerrado (503) si el servidor no tiene SESSION_SECRET configurada, en vez
    de dejar pasar todo como si no hubiera autenticación."""
    secret = os.environ.get("SESSION_SECRET")
    if not secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "SESSION_SECRET no configurada en el servidor")
    if not snarf_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no autenticado")
    user_id = verify_session_token(secret, snarf_session)
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sesión inválida o expirada")
    return user_id


def is_authenticated(snarf_session: str | None) -> bool:
    secret = os.environ.get("SESSION_SECRET")
    if not secret or not snarf_session:
        return False
    return verify_session_token(secret, snarf_session) is not None
