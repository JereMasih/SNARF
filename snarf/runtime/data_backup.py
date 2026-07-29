import shutil
import time
from pathlib import Path

DATA_DIR = Path("data")
BACKUP_DIR = Path("data_backups")

# Todo lo que es estado real e irremplazable: memoria episódica, logs de
# actividad/uso/entrada, preferencias del dashboard, caché del digest de
# Gmail, archivos locales creados/recibidos por Snarf, y los registros de
# Proyectos (nombre/prompt/tareas/notas de cada uno). Se excluye a propósito
# `drive_index/` (caché de vectores de Google Drive, cientos de MB): es
# regenerable desde la fuente real (Drive), respaldarlo sería caro y
# redundante.
BACKUP_TARGETS = [
    "activity_log.jsonl",
    "episodic_memory.jsonl",
    "input_log.jsonl",
    "manual_verification_log.jsonl",
    "usage_log.jsonl",
    "dashboard_prefs",
    "gmail_digest",
    "local_files",
    "projects",
]
KEEP_LAST_N = 14
SNAPSHOT_TIME_FORMAT = "%Y-%m-%dT%H-%M-%S"


def backup_now(
    data_dir: Path = DATA_DIR, backup_dir: Path = BACKUP_DIR, keep_last_n: int = KEEP_LAST_N, stamp: str | None = None
) -> Path:
    """Copia todo BACKUP_TARGETS a un snapshot nuevo con timestamp, y poda los
    snapshots más viejos. No falla si algún target todavía no existe (ej. un
    log que nunca se generó). `stamp` es para tests (evita depender de
    resolución real de reloj entre snapshots consecutivos)."""
    dest = backup_dir / (stamp or time.strftime(SNAPSHOT_TIME_FORMAT))
    dest.mkdir(parents=True, exist_ok=True)
    for name in BACKUP_TARGETS:
        src = data_dir / name
        if not src.exists():
            continue
        target = dest / name
        if src.is_dir():
            shutil.copytree(src, target)
        else:
            shutil.copy2(src, target)
    _prune_old_backups(backup_dir, keep_last_n)
    return dest


def _prune_old_backups(backup_dir: Path, keep_last_n: int) -> None:
    if not backup_dir.exists() or keep_last_n <= 0:
        return
    snapshots = sorted(p for p in backup_dir.iterdir() if p.is_dir())
    for old in snapshots[:-keep_last_n]:
        shutil.rmtree(old, ignore_errors=True)


def list_backups(backup_dir: Path = BACKUP_DIR) -> list[Path]:
    if not backup_dir.exists():
        return []
    return sorted((p for p in backup_dir.iterdir() if p.is_dir()), reverse=True)


def restore_latest(data_dir: Path = DATA_DIR, backup_dir: Path = BACKUP_DIR) -> Path | None:
    """Restaura el snapshot más reciente sobre data_dir. Nunca borra un
    target que el snapshot no tenga (ej. si un archivo no existía todavía
    cuando se hizo ese snapshot) — solo sobreescribe lo que sí tiene."""
    backups = list_backups(backup_dir)
    if not backups:
        return None
    latest = backups[0]
    for name in BACKUP_TARGETS:
        src = latest / name
        if not src.exists():
            continue
        dest = data_dir / name
        if src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    return latest
