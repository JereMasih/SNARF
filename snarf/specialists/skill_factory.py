"""Skill Factory (Fase H, ver ADR 0095/0102): Snarf construyendo y activando
una skill nueva de verdad, invocando a Claude Code, con confirmación
explícita en dos pasos — nunca autoridad general, cada construcción quema su
propia confirmación (Constitution Art. VII).

No hereda de `Specialist` — mismo motivo que `ProjectManager` (ver
snarf/specialists/base.py, ADR 0101): sus tres operaciones reales
(build_skill/activate/status) no comparten una sola forma de entrada/salida.

Flujo real, cuatro pasos (ver plan de expansión, Fase H):
1. Especificación — ya resuelta antes de llegar acá (Snarf conversa con el
   fundador en su propia voz, nunca esta clase).
2. Confirmación 1 (construir) — la hace `Orchestrator._tool_skill_factory_build`
   antes de llamar a `build_skill()`, mismo patrón `_pending()`/`confirmed`
   que `gmail_send_message`.
3. `build_skill()`: invoca a Claude Code real, verifica que el diff real
   (comparado contra el estado sucio de ANTES de invocarlo, para tolerar que
   el working tree ya tenga cambios reales de otra sesión en paralelo) solo
   tocó lo esperado, corre la suite real completa.
4. Confirmación 2 (activar) — la hace `Orchestrator._tool_skill_factory_activate`
   antes de llamar a `activate()`, mismo patrón otra vez. Activar reinicia el
   server real (LaunchAgent `com.snarf.server`, ver CLAUDE.md) — nunca queda
   "caliente" sin reiniciar (ver ADR 0095/0102, TOOLS se arma una sola vez al
   importar orchestrator.py)."""

import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

from snarf.capabilities.claude_code import ClaudeCode

SKILL_PROPOSALS_DIR = Path("data/skill_proposals")
MAX_STORED_SKILL_PROPOSALS = 20

# Alcance estricto de qué archivos puede tocar una construcción real (ver
# POLICY_HIGH_IMPACT_ACTIONS.md) — cualquier otro archivo tocado aborta la
# construcción antes de dejarla seguir sola.
_ALWAYS_ALLOWED_FILES = {
    "snarf/core/orchestrator.py",
    "snarf/telemetry/brain.py",
    "snarf/telemetry/verbs.py",
    "snarf/telemetry/detail.py",
}
_NEVER_ALLOWED_FILES = {"FOUNDATION.md", "CONSTITUTION.md", "CHARACTER.md", "COGNITION.md", "MASTER_MAP.md"}


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "skill"


def _default_git_dirty_files(repo_root: Path) -> set[str]:
    result = subprocess.run(["git", "status", "--porcelain"], cwd=str(repo_root), capture_output=True, text=True)
    files = set()
    for line in result.stdout.splitlines():
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ")[-1]
        files.add(path)
    return files


def _default_run_tests(repo_root: Path) -> dict:
    result = subprocess.run(
        [str(repo_root / ".venv" / "bin" / "python"), "-m", "pytest", "-q"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=300,
    )
    return {"passed": result.returncode == 0, "output": (result.stdout + result.stderr)[-3000:]}


def _default_restart() -> None:
    # Mismo procedimiento real documentado en CLAUDE.md — un kill simple no
    # alcanza con el LaunchAgent real.
    uid = os.getuid()
    plist = Path.home() / "Library" / "LaunchAgents" / "com.snarf.server.plist"
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/com.snarf.server"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)], capture_output=True, check=True)


class SkillFactorySpecialist:
    def __init__(
        self,
        claude_code: ClaudeCode,
        repo_root: Path,
        git_dirty_files_fn=None,
        run_tests_fn=None,
        restart_fn=None,
        proposals_dir: Path = SKILL_PROPOSALS_DIR,
    ):
        self._claude_code = claude_code
        self._repo_root = repo_root
        self._git_dirty_files_fn = git_dirty_files_fn or (lambda: _default_git_dirty_files(repo_root))
        self._run_tests_fn = run_tests_fn or (lambda: _default_run_tests(repo_root))
        self._restart_fn = restart_fn or _default_restart
        self._proposals_dir = proposals_dir

    def _manifest_path(self, proposal_id: str) -> Path:
        return self._proposals_dir / proposal_id / "manifest.json"

    def _index_path(self) -> Path:
        return self._proposals_dir / "index.json"

    def _load_index(self) -> list[dict]:
        path = self._index_path()
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_manifest(self, proposal_id: str, manifest: dict) -> None:
        path = self._manifest_path(proposal_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        index = self._load_index()
        index = [e for e in index if e["id"] != proposal_id]
        index.append({"id": proposal_id, "branch": manifest["branch"], "skill_name": manifest["skill_name"], "status": manifest["status"], "updated_at": manifest.get("updated_at", time.time())})
        index = index[-MAX_STORED_SKILL_PROPOSALS:]
        self._index_path().write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_manifest(self, proposal_id: str) -> dict | None:
        path = self._manifest_path(proposal_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_proposals(self) -> list[dict]:
        return self._load_index()

    def _build_prompt(self, branch: str, skill_name: str, description: str, clarifying_answers: list[dict]) -> str:
        qa_lines = (
            "\n".join(f"- {qa.get('question', '')}: {qa.get('answer', '')}" for qa in clarifying_answers)
            if clarifying_answers
            else "(sin aclaraciones adicionales)"
        )
        return (
            "Construí un Specialist nuevo para Snarf, siguiendo EXACTAMENTE la convención real del "
            "repo (ver snarf/specialists/base.py, snarf/specialists/gmail_digest.py como ejemplo real, "
            "KNOWLEDGE.md, HARNESS.md, ADR 0101):\n\n"
            f"- Rama: {branch}\n- Nombre del skill: {skill_name}\n- Descripción: {description}\n"
            f"- Aclaraciones ya resueltas con el fundador:\n{qa_lines}\n\n"
            "Pasos obligatorios, en este orden:\n"
            f"1. Creá snarf/specialists/{branch}/{skill_name}.py — clase que hereda de "
            "snarf.specialists.base.Specialist (salvo que sus operaciones no compartan una sola "
            "forma de entrada/salida, mismo criterio que ProjectManager), con docstring real, "
            "*_SYSTEM_PROMPT si usa un LLM, inyección por constructor de Capacidades ya existentes "
            "(reusalas, nunca inventes una Capacidad nueva sin necesidad real), y los dicts "
            "INPUT_SCHEMA/OUTPUT_SCHEMA a nivel de módulo.\n"
            f"2. Creá tests/test_{skill_name}.py con cobertura real del comportamiento nuevo.\n"
            "3. Sumá 1-3 tools nuevos a orchestrator.TOOLS/_tool_handlers (aditivo, nunca borres ni "
            "reescribas algo existente) y su entrada correspondiente en TOOL_TO_NODE (brain.py), "
            "VERB_BY_SKILL (verbs.py) y DETAIL_EXTRACTORS (detail.py) — los tests de cobertura ya "
            "existentes fallan si falta alguno.\n"
            "4. Corré la suite completa real (.venv/bin/python -m pytest -q) y confirmá que pasa "
            "entera, no solo los tests nuevos.\n\n"
            "Alcance estricto, NUNCA lo excedas: no edites FOUNDATION.md, CONSTITUTION.md, "
            "CHARACTER.md, COGNITION.md, ni MASTER_MAP.md. No toques ningún otro archivo de código "
            "fuera de los nombrados arriba. No hagas ningún commit ni ningún git push — eso lo hace "
            "el fundador o una sesión de Claude Code interactiva después."
        )

    def _expected_files(self, branch: str, skill_name: str) -> set[str]:
        return _ALWAYS_ALLOWED_FILES | {
            f"snarf/specialists/{branch}/{skill_name}.py",
            f"snarf/specialists/{branch}/__init__.py",
            f"tests/test_{skill_name}.py",
        }

    def build_skill(self, branch: str, skill_name: str, description: str, clarifying_answers: list[dict] | None = None) -> dict:
        clarifying_answers = clarifying_answers or []
        proposal_id = f"{_slugify(skill_name)}-{uuid.uuid4().hex[:8]}"
        manifest = {
            "id": proposal_id,
            "branch": branch,
            "skill_name": skill_name,
            "description": description,
            "clarifying_answers": clarifying_answers,
            "status": "building",
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self._save_manifest(proposal_id, manifest)

        if not self._claude_code.available:
            manifest["status"] = "failed"
            manifest["abort_reason"] = "Claude Code no está instalado en esta máquina."
            manifest["updated_at"] = time.time()
            self._save_manifest(proposal_id, manifest)
            return {"proposal_id": proposal_id, "status": "failed", "reason": manifest["abort_reason"]}

        before = self._git_dirty_files_fn()
        prompt = self._build_prompt(branch, skill_name, description, clarifying_answers)
        result = self._claude_code.run(prompt)

        after = self._git_dirty_files_fn()
        touched = after - before

        manifest["claude_code_session_id"] = result.session_id
        manifest["claude_code_cost_usd"] = result.cost_usd
        manifest["diff_files"] = sorted(touched)

        if not result.ok:
            manifest["status"] = "failed"
            manifest["abort_reason"] = f"Claude Code no terminó con éxito: {result.result_text}"
            manifest["updated_at"] = time.time()
            self._save_manifest(proposal_id, manifest)
            return {"proposal_id": proposal_id, "status": "failed", "reason": manifest["abort_reason"]}

        forbidden = touched & _NEVER_ALLOWED_FILES
        unexpected = touched - self._expected_files(branch, skill_name)
        if forbidden or unexpected:
            manifest["status"] = "aborted"
            manifest["abort_reason"] = (
                f"Tocó archivo(s) fuera del alcance autorizado: {sorted(forbidden | unexpected)}."
            )
            manifest["updated_at"] = time.time()
            self._save_manifest(proposal_id, manifest)
            return {
                "proposal_id": proposal_id,
                "status": "aborted",
                "reason": manifest["abort_reason"],
                "diff_files": manifest["diff_files"],
            }

        test_result = self._run_tests_fn()
        manifest["test_result"] = test_result
        if not test_result["passed"]:
            manifest["status"] = "failed"
            manifest["abort_reason"] = "La suite completa no pasó tras la construcción."
            manifest["updated_at"] = time.time()
            self._save_manifest(proposal_id, manifest)
            return {
                "proposal_id": proposal_id,
                "status": "failed",
                "reason": manifest["abort_reason"],
                "test_output": test_result["output"],
            }

        manifest["status"] = "built"
        manifest["updated_at"] = time.time()
        self._save_manifest(proposal_id, manifest)
        return {
            "proposal_id": proposal_id,
            "status": "built",
            "diff_files": manifest["diff_files"],
            "tests_passed": True,
            "next_step": "Para activarla hace falta reiniciar el server — confirmá con skill_factory_activate.",
        }

    def activate(self, proposal_id: str) -> dict:
        manifest = self.load_manifest(proposal_id)
        if manifest is None:
            return {"error": f"proposal '{proposal_id}' no existe."}
        if manifest["status"] != "built":
            return {"error": f"proposal '{proposal_id}' no está en estado 'built' (está en '{manifest['status']}')."}
        self._restart_fn()
        manifest["status"] = "activated"
        manifest["activated_at"] = time.time()
        manifest["updated_at"] = time.time()
        self._save_manifest(proposal_id, manifest)
        return {"proposal_id": proposal_id, "status": "activated"}

    def status(self, proposal_id: str) -> dict:
        manifest = self.load_manifest(proposal_id)
        if manifest is None:
            return {"error": f"proposal '{proposal_id}' no existe."}
        return manifest
