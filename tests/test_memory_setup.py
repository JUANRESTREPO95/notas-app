from __future__ import annotations

from app.agent_note import ensure_agent_note
from app.db import init_db
from app.memory_setup import ensure_memory_setup


def prepare(settings):
    settings.notes_dir.mkdir(parents=True, exist_ok=True)
    init_db(settings.db_path)
    ensure_agent_note(settings)


def test_memory_note_created_in_root(auth, settings):
    tree = auth.get("/api/tree").json()
    paths = {note["path"] for note in tree["notes"]}
    assert "configuracion.md" in paths
    assert "proyectos" in tree["folders"]

    content = (settings.notes_dir / "configuracion.md").read_text(encoding="utf-8")
    assert "# Configuración" in content
    assert "## Configuración" in content
    assert "## Usuario" in content
    assert "## Proyectos" in content
    assert "proyectos/<nombre>" in content
    assert "## Recordatorios" in content
    assert "POST /api/reminders" in content
    assert "Nombre:" in content


def test_agent_note_points_to_shared_memory(client, settings):
    content = (settings.notes_dir / "Agente.md").read_text(encoding="utf-8")
    assert "<!-- memoria:compartida:v4 -->" in content
    assert "configuracion.md" in content
    assert "proyectos/<nombre>" in content
    assert "Claude Code" in content
    assert "Iris/configuracion" not in content


def test_memory_setup_is_idempotent(settings):
    prepare(settings)
    first = ensure_memory_setup(settings)
    assert "configuracion.md" in first
    assert "Agente" in first

    assert ensure_memory_setup(settings) == []

    content = (settings.notes_dir / "Agente.md").read_text(encoding="utf-8")
    assert content.count("<!-- memoria:compartida:v4 -->") == 1


def test_memory_setup_migrates_old_notes(settings):
    prepare(settings)
    old = settings.notes_dir / "Iris/configuracion"
    old.mkdir(parents=True)
    (old / "configuracion.md").write_text(
        "---\nid: vieja-config\ntitle: Configuración\n---\n"
        "# Configuración de Iris\n\nTono propio\n",
        encoding="utf-8",
    )
    (old / "usuario.md").write_text(
        "---\nid: viejo-usuario\ntitle: Usuario\n---\n"
        "# Usuario\n\nNombre: Juan\n",
        encoding="utf-8",
    )

    created = ensure_memory_setup(settings)
    assert "configuracion.md" in created

    content = (settings.notes_dir / "configuracion.md").read_text(encoding="utf-8")
    assert "Tono propio" in content
    assert "Nombre: Juan" in content
    assert "# Configuración de Iris" not in content
    assert "\n# Usuario\n" not in content


def test_memory_setup_updates_old_agent_section(settings):
    prepare(settings)
    agent_path = settings.notes_dir / "Agente.md"
    agent_path.write_text(
        "---\nid: agente\ntitle: Agente\nprotected: true\n---\n"
        "Mi texto propio\n\n<!-- iris:configuracion:v2 -->\n\n## Sección vieja\n",
        encoding="utf-8",
    )

    assert "Agente" in ensure_memory_setup(settings)
    content = agent_path.read_text(encoding="utf-8")
    assert "Mi texto propio" in content
    assert "## Sección vieja" not in content
    assert "<!-- memoria:compartida:v4 -->" in content
    assert "<!-- iris:configuracion:v2 -->" not in content


def test_projects_folder_is_protected(auth):
    tree = auth.get("/api/tree").json()
    assert "proyectos" in tree["folders"]

    assert (
        auth.delete("/api/folders", params={"path": "proyectos"}).status_code == 403
    )
    assert (
        auth.delete(
            "/api/folders", params={"path": "proyectos", "recursive": "true"}
        ).status_code
        == 403
    )
    assert (
        auth.patch(
            "/api/folders", json={"path": "proyectos", "new_path": "otros"}
        ).status_code
        == 403
    )


def test_new_project_gets_context_note(auth, settings):
    assert auth.post("/api/folders", json={"path": "proyectos/demo"}).status_code == 201
    path = settings.notes_dir / "proyectos/demo/contexto.md"
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    assert "# demo" in content
    assert "## Contexto" in content

    paths = {note["path"] for note in auth.get("/api/tree").json()["notes"]}
    assert "proyectos/demo/contexto.md" in paths

    response = auth.delete(
        "/api/folders", params={"path": "proyectos/demo", "recursive": "true"}
    )
    assert response.status_code == 200
    assert (settings.notes_dir / "proyectos").is_dir()


def test_config_section_added_to_existing_note(settings):
    prepare(settings)
    path = settings.notes_dir / "configuracion.md"
    path.write_text(
        "---\nid: cfg\ntitle: Configuración\n---\n# Configuración\n\nMi texto\n",
        encoding="utf-8",
    )

    ensure_memory_setup(settings)
    content = path.read_text(encoding="utf-8")
    assert "Mi texto" in content
    assert "<!-- proyectos:inicio -->" in content
    assert content.count("<!-- proyectos:inicio -->") == 1


def test_memory_setup_does_not_overwrite_edits(settings):
    prepare(settings)
    ensure_memory_setup(settings)

    path = settings.notes_dir / "configuracion.md"
    original = path.read_text(encoding="utf-8")
    path.write_text(original + "\nMi nota adicional\n", encoding="utf-8")

    assert ensure_memory_setup(settings) == []
    assert "Mi nota adicional" in path.read_text(encoding="utf-8")
