"""Deriva la identidad real de Snarf (user_id) a partir de una cuenta de
Google verdadera — la pieza que hace de "Sign in with Google" el método
principal de alta de un usuario nuevo (Fase 3 del plan de multi-usuario,
ADR 0137). Nunca inventa un email ni un user_id: ambos salen de una
respuesta real de la API de Google, o la función levanta un error."""

import re

import requests

USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"
_REQUEST_TIMEOUT_SECONDS = 10


def fetch_email(creds) -> str:
    response = requests.get(
        USERINFO_ENDPOINT, headers={"Authorization": f"Bearer {creds.token}"}, timeout=_REQUEST_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    email = response.json().get("email")
    if not email:
        raise RuntimeError("Google no devolvió un email real para esta cuenta — no se puede identificar al usuario.")
    return email


def user_id_for_email(email: str) -> str:
    """Deriva un user_id real y estable a partir de un email de Google — la
    misma cuenta siempre produce el mismo user_id, nunca un valor aleatorio
    ni inventado. Sanitizado para ser seguro como segmento de path real
    (Orchestrator usa user_id directo en rutas de disco — ver
    MEMORY_DATA_DIR/KNOWLEDGE_DATA_DIR/DRIVE_INDEX_DATA_DIR/
    LOCAL_FILES_DATA_DIR en snarf/core/orchestrator.py). El punto NO queda
    en el allowlist a propósito (aunque es un carácter válido de email):
    dejarlo pasar permitiría que un email adversarial tipo
    "x/../../etc@gmail.com" sobreviviera como "x/.._../etc@gmail.com" y
    reconstruyera un path traversal real después de sanear solo "/" — al
    reemplazar también "." por "_", ninguna secuencia ".." puede sobrevivir
    de ningún input posible."""
    normalized = email.strip().lower()
    return re.sub(r"[^a-z0-9_@-]", "_", normalized)
