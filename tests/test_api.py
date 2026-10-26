from __future__ import annotations


def test_health(client):
    assert client.get("/api/health").json()["ok"] is True


def test_login_required(client):
    assert client.get("/api/tree").status_code == 401


def test_login_rejects_bad_password(client):
    response = client.post(
        "/api/login", json={"username": "juan", "password": "incorrecta"}
    )
    assert response.status_code == 401


def test_notes_flow(auth):
    assert auth.post("/api/folders", json={"path": "Notas"}).status_code == 201
    assert auth.post("/api/folders", json={"path": "Notas/Sub"}).status_code == 201

    response = auth.post(
        "/api/notes",
        json={"folder": "Notas", "title": "Hola Mundo", "content": "contenido de prueba"},
    )
    assert response.status_code == 201
    note = response.json()
    assert note["path"] == "Notas/hola-mundo.md"
    note_id = note["id"]

    tree = auth.get("/api/tree").json()
    assert "Notas" in tree["folders"]
    assert "Notas/Sub" in tree["folders"]
    assert any(item["id"] == note_id for item in tree["notes"])

    assert auth.get(f"/api/notes/{note_id}").json()["content"] == "contenido de prueba"

    results = auth.get("/api/search", params={"q": "prueba"}).json()["results"]
    assert any(item["id"] == note_id for item in results)

    response = auth.put(
        f"/api/notes/{note_id}", json={"title": "Hola de nuevo", "content": "otro texto"}
    )
    assert response.json()["title"] == "Hola de nuevo"
    assert response.json()["content"] == "otro texto"

    response = auth.post(f"/api/notes/{note_id}/move", json={"folder": "Notas/Sub"})
    assert response.json()["path"] == "Notas/Sub/hola-mundo.md"

    assert auth.delete(f"/api/notes/{note_id}").status_code == 200
    assert auth.get(f"/api/notes/{note_id}").status_code == 404


def test_backfill_versions(settings):
    from app.db import init_db
    from app.history import backfill_versions, list_versions
    from app.storage import scan_notes

    init_db(settings.db_path)
    folder = settings.notes_dir / "Externa"
    folder.mkdir(parents=True)
    (folder / "suelta.md").write_text(
        "---\ntitle: Suelta\n---\ncontenido\n", encoding="utf-8"
    )
    backfill_versions(settings)
    notes = scan_notes(settings.notes_dir, settings.timezone)
    versions = list_versions(settings, notes[0]["id"])
    assert len(versions) == 1
    assert versions[0]["source"] == "snapshot"


def test_note_versions_and_restore(auth):
    auth.post("/api/folders", json={"path": "Historial"})
    note = auth.post(
        "/api/notes",
        json={"folder": "Historial", "title": "Versiones", "content": "v1"},
    ).json()
    note_id = note["id"]

    versions = auth.get(f"/api/notes/{note_id}/versions").json()["versions"]
    assert len(versions) == 1
    assert versions[0]["source"] == "create"
    first_version_id = versions[0]["id"]

    auth.put(f"/api/notes/{note_id}", json={"content": "v2"})
    auth.put(f"/api/notes/{note_id}", json={"content": "v3"})
    versions = auth.get(f"/api/notes/{note_id}/versions").json()["versions"]
    assert len(versions) == 2
    assert versions[0]["source"] == "update"

    detail = auth.get(
        f"/api/notes/{note_id}/versions/{first_version_id}"
    ).json()
    assert detail["content"] == "v1"

    restored = auth.post(
        f"/api/notes/{note_id}/versions/{first_version_id}/restore"
    )
    assert restored.status_code == 200
    assert restored.json()["content"] == "v1"
    assert auth.get(f"/api/notes/{note_id}").json()["content"] == "v1"

    versions = auth.get(f"/api/notes/{note_id}/versions").json()["versions"]
    assert len(versions) == 4
    assert versions[0]["source"] == f"restore:{first_version_id}"
    assert versions[1]["source"] == "before-restore"


def test_folder_delete_requires_recursive(auth):
    auth.post("/api/folders", json={"path": "Temporal"})
    auth.post("/api/notes", json={"folder": "Temporal", "title": "Algo", "content": "x"})

    assert auth.delete("/api/folders", params={"path": "Temporal"}).status_code == 409
    response = auth.delete(
        "/api/folders", params={"path": "Temporal", "recursive": "true"}
    )
    assert response.status_code == 200


def test_path_traversal_is_rejected(auth):
    assert auth.post("/api/folders", json={"path": "../fuera"}).status_code == 400
    assert auth.post("/api/folders", json={"path": "/absoluta"}).status_code == 400
    assert auth.post("/api/folders", json={"path": "oculta/.secreta"}).status_code == 400


def test_reminders_flow(auth):
    response = auth.post(
        "/api/reminders",
        json={"title": "Llamar", "body": "a las nueve", "due_at": "2026-10-26T09:00:00-05:00"},
    )
    assert response.status_code == 201
    reminder = response.json()
    assert reminder["due_at"].startswith("2026-10-26T14:00:00")
    reminder_id = reminder["id"]

    response = auth.patch(f"/api/reminders/{reminder_id}", json={"done": True})
    assert response.json()["done"] is True

    pending = auth.get("/api/reminders", params={"done": "false"}).json()["reminders"]
    assert pending == []

    assert auth.delete(f"/api/reminders/{reminder_id}").status_code == 200
    assert auth.delete(f"/api/reminders/{reminder_id}").status_code == 404


def test_token_scopes(client):
    client.post("/api/login", json={"username": "juan", "password": "testpass123"})
    client.post("/api/folders", json={"path": "01-claude"})
    client.post("/api/folders", json={"path": "02-lectura"})
    client.post("/api/folders", json={"path": "03-privado"})
    client.post(
        "/api/notes",
        json={"folder": "01-claude", "title": "Interna", "content": "solo agente"},
    )
    client.post(
        "/api/notes",
        json={"folder": "02-lectura", "title": "Compartida", "content": "leer"},
    )

    response = client.post(
        "/api/tokens",
        json={
            "name": "claude",
            "rules": [
                {"path": "01-claude", "level": "write"},
                {"path": "02-lectura", "level": "read"},
            ],
        },
    )
    assert response.status_code == 201
    token = response.json()["token"]
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {token}"}

    tree = client.get("/api/tree", headers=headers).json()
    assert sorted(tree["folders"]) == ["01-claude", "02-lectura"]
    assert "03-privado" not in tree["folders"]

    assert (
        client.post(
            "/api/notes",
            headers=headers,
            json={"folder": "01-claude", "title": "Nueva", "content": "x"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/notes",
            headers=headers,
            json={"folder": "02-lectura", "title": "No", "content": "x"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/notes",
            headers=headers,
            json={"folder": "03-privado", "title": "No", "content": "x"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/tokens",
            headers=headers,
            json={"name": "otro", "rules": []},
        ).status_code
        == 403
    )


def test_token_names_are_unique(auth):
    first = auth.post("/api/tokens", json={"name": "repetido", "rules": []})
    assert first.status_code == 201
    second = auth.post("/api/tokens", json={"name": "repetido", "rules": []})
    assert second.status_code == 409
    auth.delete(f"/api/tokens/{first.json()['id']}")


def test_token_rules_can_be_updated(client):
    client.post("/api/login", json={"username": "juan", "password": "testpass123"})
    client.post("/api/folders", json={"path": "claude-code"})
    created = client.post(
        "/api/tokens", json={"name": "editable", "rules": []}
    ).json()
    headers = {"Authorization": f"Bearer {created['token']}"}

    client.cookies.clear()
    assert client.get("/api/tree", headers=headers).json()["folders"] == []

    client.post("/api/login", json={"username": "juan", "password": "testpass123"})
    response = client.patch(
        f"/api/tokens/{created['id']}",
        json={"rules": [{"path": "claude-code", "level": "read"}]},
    )
    assert response.status_code == 200

    client.cookies.clear()
    assert "claude-code" in client.get("/api/tree", headers=headers).json()["folders"]
    assert (
        client.post(
            "/api/notes",
            headers=headers,
            json={"folder": "claude-code", "title": "No", "content": "x"},
        ).status_code
        == 403
    )

    client.post("/api/login", json={"username": "juan", "password": "testpass123"})
    client.delete(f"/api/tokens/{created['id']}")


def test_token_revocation(client):
    client.post("/api/login", json={"username": "juan", "password": "testpass123"})
    created = client.post("/api/tokens", json={"name": "revocar", "rules": []}).json()
    headers = {"Authorization": f"Bearer {created['token']}"}

    client.cookies.clear()
    assert client.get("/api/reminders", headers=headers).status_code == 200

    client.post("/api/login", json={"username": "juan", "password": "testpass123"})
    assert client.delete(f"/api/tokens/{created['id']}").status_code == 200

    client.cookies.clear()
    assert client.get("/api/reminders", headers=headers).status_code == 401


def test_external_file_is_indexed(auth, settings):
    folder = settings.notes_dir / "Externa"
    folder.mkdir(parents=True)
    (folder / "suelta.md").write_text(
        "---\ntitle: Suelta\n---\ncontenido externo\n", encoding="utf-8"
    )

    assert auth.post("/api/reindex").status_code == 200
    results = auth.get("/api/search", params={"q": "externo"}).json()["results"]
    assert any(item["title"] == "Suelta" for item in results)

    tree = auth.get("/api/tree").json()
    assert "Externa" in tree["folders"]
    assert any(item["path"] == "Externa/suelta.md" for item in tree["notes"])


def test_seed_admin_after_rename(settings):
    from app.db import connect, init_db
    from app.main import seed_admin

    init_db(settings.db_path)
    seed_admin(settings)
    with connect(settings.db_path) as conn:
        conn.execute("UPDATE users SET username = 'otro'")
    seed_admin(settings)
    with connect(settings.db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert count == 1


def test_account_changes_username_and_password(auth):
    response = auth.put(
        "/api/account",
        json={"current_password": "testpass123", "username": "juan2"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "juan2"
    assert auth.get("/api/me").json()["name"] == "juan2"

    auth.post("/api/logout")
    assert (
        auth.post(
            "/api/login", json={"username": "juan", "password": "testpass123"}
        ).status_code
        == 401
    )
    assert (
        auth.post(
            "/api/login", json={"username": "juan2", "password": "testpass123"}
        ).status_code
        == 200
    )

    response = auth.put(
        "/api/account",
        json={"current_password": "testpass123", "new_password": "nueva12345"},
    )
    assert response.status_code == 200

    auth.post("/api/logout")
    assert (
        auth.post(
            "/api/login", json={"username": "juan2", "password": "testpass123"}
        ).status_code
        == 401
    )
    assert (
        auth.post(
            "/api/login", json={"username": "juan2", "password": "nueva12345"}
        ).status_code
        == 200
    )


def test_account_rejects_bad_current_password(auth):
    response = auth.put(
        "/api/account",
        json={"current_password": "incorrecta", "username": "otro"},
    )
    assert response.status_code == 400


def test_account_rejects_invalid_username(auth):
    response = auth.put(
        "/api/account",
        json={"current_password": "testpass123", "username": "con espacio"},
    )
    assert response.status_code == 422


def test_account_requires_a_change(auth):
    response = auth.put("/api/account", json={"current_password": "testpass123"})
    assert response.status_code == 400


def test_password_change(auth):
    response = auth.put(
        "/api/password",
        json={"current_password": "testpass123", "new_password": "nueva12345"},
    )
    assert response.status_code == 200
    auth.post("/api/logout")
    assert (
        auth.post(
            "/api/login", json={"username": "juan", "password": "testpass123"}
        ).status_code
        == 401
    )
    assert (
        auth.post(
            "/api/login", json={"username": "juan", "password": "nueva12345"}
        ).status_code
        == 200
    )
