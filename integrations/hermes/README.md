# Integración con Hermes

Hermes corre en el servidor, en el host. Cuando Notas está desplegada en Docker
en ese mismo servidor, Hermes la llama por `http://127.0.0.1:3001`.

## 1. Desplegar Notas en el servidor

```bash
cd ~/notas-app
cp .env.example .env
# Editar .env con SECRET_KEY y ADMIN_PASSWORD fuertes
docker compose up -d --build
curl http://127.0.0.1:3001/api/health
```

## 2. Crear carpetas, token y entorno de Hermes

El script hace todo y verifica permisos. No imprime el token.

```bash
cd ~/notas-app
python3 integrations/hermes/setup_server.py \
  --base http://127.0.0.1:3001 \
  --app-env .env \
  --hermes-env ~/.hermes/.env
```

Crea:

| Carpeta | Permiso de Hermes |
|---|---|
| `hermes-libre` | escritura total |
| `hermes-lectura` | solo lectura |
| `hermes-privado` | sin acceso |
| `recordatorios` | escritura |

El token queda con estas reglas:

```json
[
  {"path": "hermes-libre", "level": "write"},
  {"path": "hermes-lectura", "level": "read"},
  {"path": "recordatorios", "level": "write"}
]
```

Y escribe en `~/.hermes/.env`:

```bash
NOTAS_API_URL=http://127.0.0.1:3001
NOTAS_API_TOKEN=nsk_...
```

## 3. Instalar CLI y skill

```bash
cd ~/notas-app
install -m 700 integrations/hermes/notas_agent.py ~/.hermes/scripts/notas_agent.py
mkdir -p ~/.hermes/skills/notas/notas-reminders
install -m 644 integrations/hermes/SKILL.md ~/.hermes/skills/notas/notas-reminders/SKILL.md
```

Recargar Hermes para que lea el `.env` y la skill:

```bash
systemctl --user reload hermes-gateway.service
```

## 4. Notificaciones programadas

El servicio `notificar-recordatorios.service` envía un resumen limpio por
WhatsApp a las 8:00, 13:00 y 18:00 (America/Bogota), solo si hay pendientes.

```bash
install -m 700 integrations/hermes/notificar_recordatorios.py ~/.hermes/scripts/notificar_recordatorios.py
install -m 644 integrations/hermes/notificar-recordatorios.service ~/.config/systemd/user/notificar-recordatorios.service
systemctl --user daemon-reload
systemctl --user enable --now notificar-recordatorios.service
systemctl --user status notificar-recordatorios.service
```

Prueba sin enviar nada:

```bash
~/.hermes/scripts/notificar_recordatorios.py --dry-run
```

Los recordatorios tienen su propio estado `done`, así que no hace falta mover
notas entre carpetas para marcarlos.

## Notas

- El token se guarda en `~/.hermes/.env` (permisos 600).
- Si quieres que Hermes también escriba en otra carpeta, agrega una regla al
  token; no le des acceso total.
- Si Notas y Hermes corren en contenedores distintos, usa la URL del servicio en
  la red de Docker.