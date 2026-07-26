from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

DOCUMENTS = ["FOUNDATION.md", "CONSTITUTION.md", "CHARACTER.md"]


def load_identity() -> str:
    parts = []
    for name in DOCUMENTS:
        path = ROOT / name
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)
