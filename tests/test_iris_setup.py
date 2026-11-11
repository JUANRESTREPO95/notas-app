from __future__ import annotations

from app.agent_note import ensure_agent_note
from app.db import init_db
from app.iris_setup import ensure_iris_setup


def prepare(settings):
    settings.notes_dir.mkdir(parents=True, exist_ok=True)
    init_db(settings.db_path)
    ensure_agent_note(settings)


def test_iris_memory_structure_created(auth, settings):
    tree = auth.get("/api/tree").json()
    assert "Iris" in tree["folders"]
    assert "Iris/configuracion" in tree["folders"]

    paths = {note["path"] for note in tree["notes"]}
    assert "Iris/configuracion/configuracion.md" in paths
    assert "Iris/configuracion/usuario.md" in paths

    config = (
        settings.notes_dir / "Iris/configuracion/configuracion.md"
    ).read_text(encoding="utf-8")
    user = (settings.notes_dir / "Iris/configuracion/usuario.md").read_text(
        encoding="utf-8"
    )
    assert "# Configuración de Iris" in config
    assert "# Usuario" in user
    assert "Nombre:" in user


def test_agent_note_points_to_iris_config(client, settings):
    content = (settings.notes_dir / "Agente.md").read_text(encoding="utf-8")
    assert "<!-- iris:configuracion -->" in content
    assert "Iris/configuracion/configuracion.md" in content
    assert "Iris/configuracion/usuario.md" in content


def test_iris_setup_is_idempotent(settings):
    prepare(settings)
    first = ensure_iris_setup(settings)
    assert "Iris" in first
    assert "Iris/configuracion" in first
    assert "Iris/configuracion/configuracion.md" in first
    assert "Iris/configuracion/usuario.md" in first
    assert "Agente" in first

    second = ensure_iris_setup(settings)
    assert second == []

    content = (settings.notes_dir / "Agente.md").read_text(encoding="utf-8")
    assert content.count("<!-- iris:configuracion -->") == 1


def test_iris_setup_does_not_overwrite_edits(settings):
    prepare(settings)
    ensure_iris_setup(settings)

    user_path = settings.notes_dir / "Iris/configuracion/usuario.md"
    user_path.write_text(
        "---\nid: usuario-editado\ntitle: Usuario\n---\nmi texto\n",
        encoding="utf-8",
    )

    assert ensure_iris_setup(settings) == []
    assert "mi texto" in user_path.read_text(encoding="utf-8")
