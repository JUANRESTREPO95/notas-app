from __future__ import annotations


def test_login_page(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "Entrar" in response.text


def test_notes_requires_login(client):
    response = client.get("/notes", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_login_flow_and_shell(client):
    response = client.post(
        "/login",
        data={"username": "juan", "password": "testpass123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/notes"

    page = client.get("/notes")
    assert page.status_code == 200
    assert "Recordatorios" in page.text
    assert 'class="sidebar-quick"' in page.text
    assert "Buscar notas" in page.text


def test_note_page_renders_selected_note(auth):
    auth.post("/api/folders", json={"path": "Notas"})
    note = auth.post(
        "/api/notes",
        json={"folder": "Notas", "title": "Mi nota", "content": "Hola **mundo**"},
    ).json()

    page = auth.get(f"/notes?note={note['id']}")
    assert page.status_code == 200
    assert "Mi nota" in page.text
    assert "Vista previa" in page.text
    assert "Notas/mi-nota.md" in page.text
    assert 'data-format="bold"' in page.text
    assert 'data-format="h1"' in page.text
    assert 'data-format="table"' in page.text
    assert 'data-format="checklist"' in page.text
    assert 'data-format="hr"' in page.text
    assert 'id="history-note-btn"' in page.text
    assert 'id="history-dialog"' in page.text


def test_preview_renders_table_checklist_and_rule(auth):
    content = (
        "| A | B |\n| --- | --- |\n| 1 | 2 |\n\n"
        "---\n\n"
        "- [ ] pendiente\n- [x] hecha\n"
    )
    response = auth.post("/partials/preview", data={"content": content})
    assert response.status_code == 200
    assert "<table>" in response.text
    assert "<hr" in response.text
    assert 'type="checkbox"' in response.text
    assert "checked" in response.text
    assert "pendiente" in response.text


def test_preview_sanitizes_html(auth):
    response = auth.post(
        "/partials/preview",
        data={"content": "# Hola\n\n**mundo** <script>alert(1)</script>"},
    )
    assert response.status_code == 200
    assert "<h1>Hola</h1>" in response.text
    assert "<strong>mundo</strong>" in response.text
    assert "<script>" not in response.text


def test_reminders_page(client):
    client.post("/login", data={"username": "juan", "password": "testpass123"})
    response = client.get("/reminders")
    assert response.status_code == 200
    assert "Nuevo recordatorio" in response.text


def test_settings_page(client):
    client.post("/login", data={"username": "juan", "password": "testpass123"})
    response = client.get("/settings")
    assert response.status_code == 200
    assert "Cambiar usuario" in response.text
    assert "Cambiar contraseña" in response.text
    assert 'id="username-form"' in response.text
    assert 'id="password-form"' in response.text
    assert 'id="token-form"' in response.text
    assert 'id="token-list"' in response.text
    assert "Nuevo token" in response.text


def test_reminder_body_renders_markdown(auth):
    auth.post(
        "/api/reminders",
        json={
            "title": "Con formato",
            "body": "Esto es **fuerte**\n\n- uno\n- dos",
        },
    )
    page = auth.get("/reminders")
    assert page.status_code == 200
    assert "<strong>fuerte</strong>" in page.text
    assert "<li>uno</li>" in page.text
