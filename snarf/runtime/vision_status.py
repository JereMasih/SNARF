import re
from pathlib import Path

ROADMAP_PATH = Path("ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md")
CHANGELOG_PATH = Path("CHANGELOG.md")
ADR_DIR = Path("adr")
TESTS_DIR = Path("tests")

_ESTADO_HEADING = re.compile(r"^## Estado actual", re.MULTILINE)
_MARK_HEADING = re.compile(r'^## Norte del plan: "Mark 1" vs\. "Mark 2"', re.MULTILINE)
_CHANGELOG_ENTRY = re.compile(
    r"^## \[(?P<date>\d{4}-\d{2}-\d{2})\] (?P<title>.+?)(?: \(ADR (?P<adr>\d+)\))?$",
    re.MULTILINE,
)
_FASE_NUMBER = re.compile(r"Fase (\d+)")
_TEST_DEF = re.compile(r"^def test_", re.MULTILINE)


def _first_paragraph_after(text: str, heading: re.Pattern) -> str | None:
    """Devuelve el primer párrafo (hasta la primera línea en blanco) que
    sigue a un heading real de un .md del repo — nunca un resumen escrito a
    mano, siempre el texto real ya presente en el documento (Principio VI,
    FOUNDATION.md: GET /vision/status no hardcodea números ni prosa)."""
    match = heading.search(text)
    if match is None:
        return None
    line_end = text.find("\n", match.end())
    if line_end == -1:
        return None
    rest = text[line_end:].lstrip("\n")
    lines: list[str] = []
    for line in rest.splitlines():
        if line.strip() == "":
            break
        lines.append(line)
    return " ".join(lines).strip() or None


def _roadmap_status(path: Path) -> dict:
    if not path.exists():
        return {"summary": None, "mark_note": None, "latest_phase": None}
    text = path.read_text(encoding="utf-8")
    summary = _first_paragraph_after(text, _ESTADO_HEADING)
    mark_note = _first_paragraph_after(text, _MARK_HEADING)
    phase_numbers = [int(n) for n in _FASE_NUMBER.findall(summary or "")]
    return {
        "summary": summary,
        "mark_note": mark_note,
        "latest_phase": max(phase_numbers) if phase_numbers else None,
    }


def _changelog_recent(path: Path, limit: int = 5) -> list[dict]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    entries = []
    for m in _CHANGELOG_ENTRY.finditer(text):
        entries.append({
            "date": m.group("date"),
            "title": m.group("title").strip(),
            "adr": int(m.group("adr")) if m.group("adr") else None,
        })
    return entries[:limit]


def _adr_count(adr_dir: Path) -> int:
    if not adr_dir.exists():
        return 0
    return len(list(adr_dir.glob("*.md")))


def _test_function_count(tests_dir: Path) -> int:
    if not tests_dir.exists():
        return 0
    total = 0
    for path in tests_dir.glob("test_*.py"):
        total += len(_TEST_DEF.findall(path.read_text(encoding="utf-8")))
    return total


def build_status(
    roadmap_path: Path | None = None,
    changelog_path: Path | None = None,
    adr_dir: Path | None = None,
    tests_dir: Path | None = None,
) -> dict:
    """Estado de desarrollo real de Snarf para la página pública GET /vision
    (densidad tipo LangChain: paneles de datos, no ilustraciones) — cada
    número se lee de los archivos reales del repo en el momento del
    request, nunca se cachea ni se hardcodea (ADR nuevo de esta página)."""
    return {
        "roadmap": _roadmap_status(roadmap_path or ROADMAP_PATH),
        "changelog_recent": _changelog_recent(changelog_path or CHANGELOG_PATH),
        "adr_count": _adr_count(adr_dir or ADR_DIR),
        "test_function_count": _test_function_count(tests_dir or TESTS_DIR),
    }
