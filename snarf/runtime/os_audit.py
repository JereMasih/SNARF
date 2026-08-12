"""Auditoría real de solo lectura del propio repo de Snarf — versión Python
del mismo chequeo que ya existe como Skill de Claude Code
(`.claude/skills/os-audit/SKILL.md`), reimplementada acá porque esa Skill
solo corre dentro de una sesión de Claude Code, nunca desde el chat propio
de Snarf. Mismo criterio que `introspection.py`: este módulo devuelve
señales crudas y estructuradas — nunca un reporte narrado ya armado, eso lo
arma el modelo a partir de estos datos (ver `system_snapshot`)."""

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Extensiones que hacen que un token entre backticks cuente como "path real"
# aunque no tenga barra (ej. `MASTER_MAP.md`).
PATH_EXTENSIONS = {
    "md", "py", "json", "jsonl", "plist", "html", "yml", "yaml", "txt", "sh", "cfg", "toml",
}
_CODE_NOISE_CHARS = set("()=<>{}\"'`")

# Archivos esperables en la raíz de un repo Snarf real (manual operativo,
# gobernanza, config estándar) — cualquier otra cosa suelta ahí es hallazgo.
ROOT_ALLOWED_FILES = {
    "CLAUDE.md", "README.md", "LICENSE", ".gitignore", ".env.example",
    "MASTER_MAP.md", "CHANGELOG.md", "FOUNDATION.md", "CONSTITUTION.md",
    "CHARACTER.md", "COGNITION.md", "KNOWLEDGE.md", "TELEMETRY_SCHEMA.md",
    "POLICY_HIGH_IMPACT_ACTIONS.md", "PROJECT_CONTEXT.md", "SESSION_STATE.md",
    "HARNESS.md", "ARCHITECTURE_AUDIT.md", "VPS_MIGRATION.md",
    "IMAGE_GENERATION_RESEARCH.md",
    "app.py", "main.py", "mcp_server.py",
    "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
    "pytest.ini", "server_8002.log",
}
# Prefijos/patrones de raíz legítimos que no tienen un nombre fijo (varios
# roadmaps vivos, varios docker-compose por servicio, requirements por
# entorno) — se chequean aparte del set exacto de arriba.
ROOT_ALLOWED_PATTERNS = (
    re.compile(r"^ROADMAP.*\.md$"),
    re.compile(r"^docker-compose.*\.ya?ml$"),
    re.compile(r"^requirements.*\.txt$"),
)
ROOT_ALLOWED_DIRS = {
    ".git", ".github", ".venv", "venv", "__pycache__", ".pytest_cache",
    "data", "data_backups", "credentials", "logs", ".claude",
    "adr", "snarf", "tests", "web", "n8n_workflows", "n8n_data", "audits",
}
# .env.example es el template sancionado (sin secretos) — nunca un hallazgo.
SUSPICIOUS_TRACKED_PATTERNS = re.compile(
    r"(^|/)(\.env(?!\.example$)(\..+)?|.*credentials.*\.json|.*service[-_]account.*\.json|.*secret.*\.json|id_rsa|.*\.pem)$",
    re.IGNORECASE,
)


def _run_git(args: list[str], repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=repo_root, capture_output=True, text=True, timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


# Pares de palabras que aparecen seguido en prosa técnica entre backticks
# ("`if/elif`", "`try/except`") y calzan con el patrón "tiene una barra" sin
# ser un path real — denylist chica a propósito, no un parser de inglés.
_WORD_PAIR_NOISE = {
    "if/elif", "if/else", "try/except", "and/or", "read/write",
    "request/response", "get/post", "input/output",
}


def _extract_paths(text: str) -> list[str]:
    """Candidatos a path reales dentro de spans entre backticks — filtra
    identificadores de código (llamadas, asignaciones, tipos) que también
    caen en un `` `...` `` pero no son un path."""
    candidates = []
    for token in re.findall(r"`([^`\n]+)`", text):
        token = token.strip()
        if not token or " " in token or any(c in _CODE_NOISE_CHARS for c in token):
            continue
        if token.lower() in _WORD_PAIR_NOISE:
            continue
        if "://" in token or "YYYY" in token:
            continue
        has_slash = "/" in token.rstrip("/")
        ext = token.rsplit(".", 1)[-1].lower() if "." in token.rsplit("/", 1)[-1] else ""
        if has_slash or ext in PATH_EXTENSIONS or token.endswith("/"):
            candidates.append(token)
    return candidates


def _resolve_and_check(token: str, repo_root: Path) -> dict | None:
    if token.startswith("~"):
        resolved = Path(token).expanduser()
        return {"path": token, "kind": "external", "exists": resolved.exists()}
    if token.startswith("/"):
        # Rutas absolutas cortas entre backticks en este repo suelen ser
        # endpoints HTTP o slash-commands (`/send`, `/clear`), no paths de
        # filesystem — solo se chequean las que parecen un path real del
        # sistema (varios segmentos, ej. `/opt/homebrew/bin/docker`).
        if len([seg for seg in token.split("/") if seg]) < 3:
            return None
        return {"path": token, "kind": "external", "exists": Path(token).exists()}
    clean = token[2:] if token.startswith("./") else token
    resolved = repo_root / clean
    return {"path": token, "kind": "repo", "exists": resolved.exists()}


def routing_check(repo_root: Path = REPO_ROOT) -> dict:
    """Check 1 de la Skill: ¿todo lo que el manual operativo referencia
    existe de verdad en disco? Y a la inversa, ¿hay carpetas reales de
    primer nivel que el manual ni menciona?"""
    manual_files = ["CLAUDE.md", "MASTER_MAP.md"]
    combined_text = []
    manuals_found = []
    for name in manual_files:
        f = repo_root / name
        if f.exists():
            manuals_found.append(name)
            combined_text.append(f.read_text(errors="ignore"))
    text = "\n".join(combined_text)

    seen: dict[str, dict] = {}
    for token in _extract_paths(text):
        if token in seen:
            continue
        checked = _resolve_and_check(token, repo_root)
        if checked is not None:
            seen[token] = checked

    missing_in_repo = [v["path"] for v in seen.values() if v["kind"] == "repo" and not v["exists"]]
    missing_external = [v["path"] for v in seen.values() if v["kind"] == "external" and not v["exists"]]

    top_level_dirs = sorted(
        p.name for p in repo_root.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name not in {"__pycache__"}
    )
    unmapped_dirs = [d for d in top_level_dirs if d.lower() not in text.lower()]

    return {
        "manuals_found": manuals_found,
        "referenced_paths_checked": len(seen),
        "dead_paths_in_repo": sorted(missing_in_repo),
        "dead_external_paths": sorted(missing_external),
        "top_level_dirs": top_level_dirs,
        "unmapped_dirs": unmapped_dirs,
    }


def _latest_adr(repo_root: Path) -> dict | None:
    adr_dir = repo_root / "adr"
    if not adr_dir.is_dir():
        return None
    files = sorted(adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md"), reverse=True)
    if not files:
        return None
    latest = files[0]
    date = _run_git(["log", "-1", "--format=%cs", "--", str(latest.relative_to(repo_root))], repo_root)
    return {
        "count": len(files),
        "latest_file": latest.name,
        "latest_commit_date": (date or "").strip() or None,
    }


def _changelog_freshness(repo_root: Path) -> dict | None:
    changelog = repo_root / "CHANGELOG.md"
    if not changelog.exists():
        return None
    text = changelog.read_text(errors="ignore")
    heading_match = re.search(r"^## \[(\d{4}-\d{2}-\d{2})\]", text, re.MULTILINE)
    entry_count = len(re.findall(r"^## \[", text, re.MULTILINE))
    return {
        "latest_entry_date": heading_match.group(1) if heading_match else None,
        "total_entries": entry_count,
    }


def _roadmap_freshness(repo_root: Path) -> list[dict]:
    out = []
    for f in sorted(repo_root.glob("ROADMAP*.md")):
        date = _run_git(["log", "-1", "--format=%cs", "--", f.name], repo_root)
        text = f.read_text(errors="ignore")
        estado = re.search(r"#+\s*Estado actual(.{0,300})", text, re.IGNORECASE | re.DOTALL)
        out.append({
            "file": f.name,
            "last_commit_date": (date or "").strip() or None,
            "estado_actual_snippet": (estado.group(1).strip()[:300] if estado else None),
        })
    return out


def freshness_check(repo_root: Path = REPO_ROOT) -> dict:
    """Check 3 de la Skill: fechas reales de los feeds que este repo trata
    como vigentes (ADRs, CHANGELOG, roadmaps) — nunca inferidas, siempre de
    `git log` o del propio contenido fechado."""
    return {
        "adr": _latest_adr(repo_root),
        "changelog": _changelog_freshness(repo_root),
        "roadmaps": _roadmap_freshness(repo_root),
    }


def root_hygiene_check(repo_root: Path = REPO_ROOT) -> dict:
    """Check 4/6 de la Skill: archivos sueltos en la raíz que no son ni el
    manual ni gobernanza ni config estándar, y el peso en palabras de los
    archivos que se cargan siempre (CLAUDE.md)."""
    loose_files = []
    for p in sorted(repo_root.iterdir()):
        if p.is_dir():
            if p.name not in ROOT_ALLOWED_DIRS and not p.name.startswith("."):
                loose_files.append({"name": p.name, "kind": "dir_not_in_map"})
            continue
        if p.name in ROOT_ALLOWED_FILES or p.name.startswith("."):
            continue
        if any(pattern.match(p.name) for pattern in ROOT_ALLOWED_PATTERNS):
            continue
        loose_files.append({"name": p.name, "kind": "loose_file", "bytes": p.stat().st_size})

    claude_md = repo_root / "CLAUDE.md"
    always_loaded_word_count = (
        len(claude_md.read_text(errors="ignore").split()) if claude_md.exists() else None
    )

    return {
        "loose_at_root": loose_files[:50],
        "claude_md_word_count": always_loaded_word_count,
    }


def git_hygiene_check(repo_root: Path = REPO_ROOT) -> dict:
    """Check 5 de la Skill: secretos trackeados y .gitignore real."""
    tracked = _run_git(["ls-files"], repo_root)
    if tracked is None:
        return {"git_available": False}
    tracked_files = tracked.splitlines()
    suspicious = [f for f in tracked_files if SUSPICIOUS_TRACKED_PATTERNS.search(f)]

    gitignore = repo_root / ".gitignore"
    gitignore_text = gitignore.read_text(errors="ignore") if gitignore.exists() else ""
    env_ignored = bool(re.search(r"^\.env$|^\.env\*", gitignore_text, re.MULTILINE))

    status = _run_git(["status", "--short"], repo_root) or ""
    dirty_entries = [line for line in status.splitlines() if line.strip()]

    return {
        "git_available": True,
        "tracked_file_count": len(tracked_files),
        "suspicious_tracked_files": suspicious,
        "env_covered_by_gitignore": env_ignored,
        "uncommitted_changes_count": len(dirty_entries),
    }


def skills_and_agents_check(repo_root: Path = REPO_ROOT) -> dict:
    """Check 5 de la Skill: skills/agents de `.claude/` que nunca cargan
    porque el archivo no se llama exactamente `SKILL.md`, o cuyo
    frontmatter no tiene `name`/`description` reales."""
    skills_dir = repo_root / ".claude" / "skills"
    broken_skills = []
    ok_skills = []
    if skills_dir.is_dir():
        for folder in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            skill_file = folder / "SKILL.md"
            if not skill_file.exists():
                broken_skills.append({"folder": folder.name, "issue": "sin SKILL.md"})
                continue
            text = skill_file.read_text(errors="ignore")
            has_name = bool(re.search(r"^name:\s*\S+", text, re.MULTILINE))
            has_desc = bool(re.search(r"^description:\s*\S+", text, re.MULTILINE))
            if has_name and has_desc:
                ok_skills.append(folder.name)
            else:
                broken_skills.append({"folder": folder.name, "issue": "frontmatter incompleto"})

    agents_dir = repo_root / ".claude" / "agents"
    agents = sorted(p.name for p in agents_dir.glob("*.md")) if agents_dir.is_dir() else []

    return {"skills_ok": ok_skills, "skills_broken": broken_skills, "agents": agents}


def run_audit(*, repo_root: Path = REPO_ROOT) -> dict:
    """Punto de entrada real del tool `os_audit` — un solo dict con todas
    las señales crudas de los checks read-only, para que el modelo arme el
    reporte narrado (mismo patrón que `system_snapshot`)."""
    return {
        "repo_root": str(repo_root),
        "routing": routing_check(repo_root),
        "freshness": freshness_check(repo_root),
        "root_hygiene": root_hygiene_check(repo_root),
        "git_hygiene": git_hygiene_check(repo_root),
        "skills_and_agents": skills_and_agents_check(repo_root),
    }
