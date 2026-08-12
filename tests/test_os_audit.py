import subprocess

from snarf.runtime import os_audit


def _git_init(repo: "os_audit.Path") -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=str(repo), check=True)


def _git_commit_all(repo: "os_audit.Path", message: str = "commit") -> None:
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=str(repo), check=True)


# --- routing_check -----------------------------------------------------


def test_routing_check_flags_a_dead_path_referenced_in_claude_md(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("Ver `snarf/runtime/no_existe.py` para más contexto.")

    result = os_audit.routing_check(tmp_path)

    assert "snarf/runtime/no_existe.py" in result["dead_paths_in_repo"]


def test_routing_check_does_not_flag_a_path_that_exists(tmp_path):
    (tmp_path / "adr").mkdir()
    (tmp_path / "adr" / "0001-real.md").write_text("real")
    (tmp_path / "CLAUDE.md").write_text("Ver `adr/0001-real.md` para más contexto.")

    result = os_audit.routing_check(tmp_path)

    assert "adr/0001-real.md" not in result["dead_paths_in_repo"]


def test_routing_check_flags_a_real_top_level_dir_not_mentioned_in_the_manual(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("Nada relevante acá.")
    (tmp_path / "n8n_workflows").mkdir()

    result = os_audit.routing_check(tmp_path)

    assert "n8n_workflows" in result["unmapped_dirs"]


def test_routing_check_ignores_urls_and_short_http_routes(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(
        "Ver `https://github.com/JereMasih/SNARF` y el endpoint `/send` para más contexto."
    )

    result = os_audit.routing_check(tmp_path)

    assert result["dead_paths_in_repo"] == []
    assert result["dead_external_paths"] == []


def test_routing_check_treats_a_long_absolute_path_as_external(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("Requiere `/opt/homebrew/bin/docker-inexistente-xyz` autorizado.")

    result = os_audit.routing_check(tmp_path)

    assert "/opt/homebrew/bin/docker-inexistente-xyz" in result["dead_external_paths"]
    assert result["dead_paths_in_repo"] == []


def test_routing_check_never_confuses_a_hidden_directory_with_a_relative_marker(tmp_path):
    (tmp_path / ".claude" / "skills" / "os-audit").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "os-audit" / "SKILL.md").write_text("---\nname: x\n---")
    (tmp_path / "CLAUDE.md").write_text("Ver `.claude/skills/os-audit/`.")

    result = os_audit.routing_check(tmp_path)

    assert ".claude/skills/os-audit/" not in result["dead_paths_in_repo"]


# --- freshness_check -----------------------------------------------------


def test_freshness_check_reports_the_latest_adr_and_changelog_entry(tmp_path):
    (tmp_path / "adr").mkdir()
    (tmp_path / "adr" / "0001-primero.md").write_text("primero")
    (tmp_path / "adr" / "0002-segundo.md").write_text("segundo")
    (tmp_path / "CHANGELOG.md").write_text("# CHANGELOG\n\n## [2026-08-12] Algo\n\n## [2026-08-01] Otro\n")

    result = os_audit.freshness_check(tmp_path)

    assert result["adr"]["count"] == 2
    assert result["adr"]["latest_file"] == "0002-segundo.md"
    assert result["changelog"]["latest_entry_date"] == "2026-08-12"
    assert result["changelog"]["total_entries"] == 2


def test_freshness_check_handles_a_repo_with_no_adr_dir(tmp_path):
    result = os_audit.freshness_check(tmp_path)
    assert result["adr"] is None


# --- root_hygiene_check -----------------------------------------------------


def test_root_hygiene_check_flags_a_loose_file_at_root(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("manual")
    (tmp_path / "server.log").write_text("log viejo")

    result = os_audit.root_hygiene_check(tmp_path)

    names = {f["name"] for f in result["loose_at_root"]}
    assert "server.log" in names


def test_root_hygiene_check_allows_roadmap_and_docker_compose_patterns(tmp_path):
    (tmp_path / "ROADMAP_ALGO.md").write_text("plan")
    (tmp_path / "docker-compose.voice.yml").write_text("services: {}")
    (tmp_path / "requirements-dev.txt").write_text("pytest")

    result = os_audit.root_hygiene_check(tmp_path)

    assert result["loose_at_root"] == []


# --- git_hygiene_check -----------------------------------------------------


def test_git_hygiene_check_reports_unavailable_outside_a_git_repo(tmp_path):
    result = os_audit.git_hygiene_check(tmp_path)
    assert result["git_available"] is False


def test_git_hygiene_check_flags_a_tracked_env_file(tmp_path):
    _git_init(tmp_path)
    (tmp_path / ".env").write_text("SECRET=x")
    _git_commit_all(tmp_path)

    result = os_audit.git_hygiene_check(tmp_path)

    assert ".env" in result["suspicious_tracked_files"]


def test_git_hygiene_check_never_flags_the_tracked_env_example_template(tmp_path):
    _git_init(tmp_path)
    (tmp_path / ".env.example").write_text("SECRET=")
    _git_commit_all(tmp_path)

    result = os_audit.git_hygiene_check(tmp_path)

    assert result["suspicious_tracked_files"] == []


def test_git_hygiene_check_reports_whether_env_is_covered_by_gitignore(tmp_path):
    _git_init(tmp_path)
    (tmp_path / ".gitignore").write_text(".env\n__pycache__/\n")
    _git_commit_all(tmp_path)

    result = os_audit.git_hygiene_check(tmp_path)

    assert result["env_covered_by_gitignore"] is True


# --- skills_and_agents_check -----------------------------------------------------


def test_skills_and_agents_check_flags_a_skill_folder_missing_skill_md(tmp_path):
    broken = tmp_path / ".claude" / "skills" / "roto"
    broken.mkdir(parents=True)
    (broken / "notes.md").write_text("no es SKILL.md")

    result = os_audit.skills_and_agents_check(tmp_path)

    assert any(s["folder"] == "roto" for s in result["skills_broken"])
    assert "roto" not in result["skills_ok"]


def test_skills_and_agents_check_accepts_a_well_formed_skill(tmp_path):
    ok = tmp_path / ".claude" / "skills" / "os-audit"
    ok.mkdir(parents=True)
    (ok / "SKILL.md").write_text("---\nname: os-audit\ndescription: algo real\n---\n")

    result = os_audit.skills_and_agents_check(tmp_path)

    assert result["skills_ok"] == ["os-audit"]
    assert result["skills_broken"] == []


# --- run_audit -----------------------------------------------------


def test_run_audit_returns_every_section(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("manual real")

    result = os_audit.run_audit(repo_root=tmp_path)

    assert set(result.keys()) == {
        "repo_root", "routing", "freshness", "root_hygiene", "git_hygiene", "skills_and_agents",
    }
