from __future__ import annotations

from fastapi.testclient import TestClient


def test_agent_note_created_and_public(client, settings):
    assert (settings.notes_dir / "Agente.md").is_file()

    response = client.get("/agente")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.headers["cache-control"] == "no-store"
    assert "# Agente" in response.text
    assert "no se puede borrar" in response.text

    alias = client.get("/agente.md")
    assert alias.status_code == 200
    assert alias.text == response.text


def test_agent_note_is_protected(auth):
    tree = auth.get("/api/tree").json()
    agent = next(item for item in tree["notes"] if item["id"] == "agente")
    assert agent["protected"] is True
    assert agent["path"] == "Agente.md"

    response = auth.delete("/api/notes/agente")
    assert response.status_code == 403
    assert auth.get("/api/notes/agente").status_code == 200


def test_agent_note_is_editable(auth):
    response = auth.put("/api/notes/agente", json={"content": "nuevo bootstrap"})
    assert response.status_code == 200
    assert response.json()["protected"] is True
    assert auth.get("/agente").text == "nuevo bootstrap"

    renamed = auth.put(
        "/api/notes/agente", json={"title": "Agente principal", "content": "otra cosa"}
    )
    assert renamed.status_code == 200
    assert auth.get("/agente").text == "otra cosa"


def test_agent_note_recreated_if_file_disappears(app, settings):
    path = settings.notes_dir / "Agente.md"

    with TestClient(app):
        assert path.is_file()
        path.unlink()
        assert not path.is_file()

    with TestClient(app) as client:
        assert path.is_file()
        assert client.get("/agente").status_code == 200


def test_agent_note_page_hides_delete_button(auth):
    page = auth.get("/notes?note=agente")
    assert page.status_code == 200
    assert 'id="delete-note-btn"' not in page.text
    assert "nota del sistema" in page.text


def test_folder_with_agent_note_cannot_be_deleted_recursively(auth):
    assert auth.post("/api/folders", json={"path": "sistema"}).status_code == 201
    moved = auth.post("/api/notes/agente/move", json={"folder": "sistema"})
    assert moved.status_code == 200
    assert moved.json()["path"] == "sistema/Agente.md"

    response = auth.delete(
        "/api/folders", params={"path": "sistema", "recursive": "true"}
    )
    assert response.status_code == 409
    assert auth.get("/agente").status_code == 200
