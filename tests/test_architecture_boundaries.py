import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Capacidades y Especialistas deben poder usarse desde un proyecto/agente
# futuro sin arrastrar a Snarf entero: nunca deben importar el Orchestrator,
# el runtime web, ni app.py. Reciben sus dependencias por inyección en el
# constructor (ver ADR 0026), no las buscan ellos mismos.
FORBIDDEN_PREFIXES = ("snarf.core", "snarf.runtime")


def _imports_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _reusable_layer_files():
    for directory in ("snarf/capabilities", "snarf/specialists"):
        yield from (ROOT / directory).glob("*.py")


def test_capabilities_and_specialists_never_import_orchestrator_or_web_runtime():
    offenders = []
    for path in _reusable_layer_files():
        for module in _imports_in(path):
            if any(module == prefix or module.startswith(prefix + ".") for prefix in FORBIDDEN_PREFIXES):
                offenders.append(f"{path.relative_to(ROOT)} imports {module}")
    assert offenders == [], (
        "Capacidades/Especialistas deben ser reusables fuera de Snarf; "
        f"no pueden importar snarf.core ni snarf.runtime: {offenders}"
    )


def test_capabilities_and_specialists_never_import_app_module():
    offenders = []
    for path in _reusable_layer_files():
        if "app" in _imports_in(path):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"No deben importar app.py (acoplaría a este servidor web): {offenders}"
