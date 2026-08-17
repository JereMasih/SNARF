from snarf.runtime import vision_status

ROADMAP_FIXTURE = """# Roadmap de prueba

## Estado actual (retomar una sesión nueva desde acá)

**Última actualización:** 2026-01-01. Hechas: Fase 1 + Fase 2 + Fase 3.

Párrafo siguiente que no debe incluirse en el resumen.

---

## Norte del plan: "Mark 1" vs. "Mark 2"

Encuadre de prueba: Mark 1 se considera terminado cuando alcance
capacidad real de auto-extensión.

## Contexto

Otro contenido irrelevante.
"""

CHANGELOG_FIXTURE = """# CHANGELOG

## [2026-01-03] Tercer cambio (ADR 0003)

Detalle.

## [2026-01-02] Segundo cambio (ADR 0002)

Detalle.

## [2026-01-01] Primer cambio sin ADR

Detalle.
"""


def _write_roadmap(tmp_path):
    path = tmp_path / "roadmap.md"
    path.write_text(ROADMAP_FIXTURE, encoding="utf-8")
    return path


def _write_changelog(tmp_path):
    path = tmp_path / "changelog.md"
    path.write_text(CHANGELOG_FIXTURE, encoding="utf-8")
    return path


def test_roadmap_status_extracts_first_paragraph_and_latest_phase(tmp_path):
    result = vision_status.build_status(
        roadmap_path=_write_roadmap(tmp_path),
        changelog_path=tmp_path / "no_existe.md",
        adr_dir=tmp_path / "no_existe_dir",
        tests_dir=tmp_path / "no_existe_dir2",
    )
    roadmap = result["roadmap"]
    assert "Fase 1 + Fase 2 + Fase 3" in roadmap["summary"]
    assert "Párrafo siguiente" not in roadmap["summary"]
    assert roadmap["latest_phase"] == 3
    assert "Mark 1" in roadmap["mark_note"]


def test_roadmap_status_with_missing_file_is_all_none(tmp_path):
    result = vision_status.build_status(
        roadmap_path=tmp_path / "no_existe.md",
        changelog_path=tmp_path / "no_existe.md",
        adr_dir=tmp_path / "no_existe_dir",
        tests_dir=tmp_path / "no_existe_dir2",
    )
    assert result["roadmap"] == {"summary": None, "mark_note": None, "latest_phase": None}


def test_changelog_recent_parses_date_title_and_adr(tmp_path):
    result = vision_status.build_status(
        roadmap_path=tmp_path / "no_existe.md",
        changelog_path=_write_changelog(tmp_path),
        adr_dir=tmp_path / "no_existe_dir",
        tests_dir=tmp_path / "no_existe_dir2",
    )
    entries = result["changelog_recent"]
    assert entries[0] == {"date": "2026-01-03", "title": "Tercer cambio", "adr": 3}
    assert entries[2] == {"date": "2026-01-01", "title": "Primer cambio sin ADR", "adr": None}


def test_adr_count_and_test_function_count_are_real(tmp_path):
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    (adr_dir / "0001-uno.md").write_text("x", encoding="utf-8")
    (adr_dir / "0002-dos.md").write_text("x", encoding="utf-8")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_algo.py").write_text("def test_a():\n    pass\n\n\ndef test_b():\n    pass\n", encoding="utf-8")
    (tests_dir / "not_a_test_file.py").write_text("def test_c():\n    pass\n", encoding="utf-8")

    result = vision_status.build_status(
        roadmap_path=tmp_path / "no_existe.md",
        changelog_path=tmp_path / "no_existe.md",
        adr_dir=adr_dir,
        tests_dir=tests_dir,
    )
    assert result["adr_count"] == 2
    assert result["test_function_count"] == 2


def test_build_status_against_real_repo_files_returns_non_empty_data():
    result = vision_status.build_status()
    assert result["adr_count"] > 0
    assert result["test_function_count"] > 0
    assert result["roadmap"]["summary"]
