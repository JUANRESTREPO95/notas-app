#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# El venv vive en WSL, no en /mnt/e, para evitar problemas de symlinks en drvfs.
VENV_DIR="${VENV_DIR:-$HOME/.venvs/notas-app}"
UV="${UV:-$(command -v uv || true)}"
if [ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ]; then
    UV="$HOME/.local/bin/uv"
fi

if [ ! -d "$VENV_DIR" ]; then
    if [ -n "$UV" ]; then
        "$UV" venv --python 3.13 "$VENV_DIR"
    else
        python3 -m venv "$VENV_DIR"
    fi
fi

if [ -n "$UV" ]; then
    "$UV" pip install --python "$VENV_DIR/bin/python" -r requirements-dev.txt
else
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    pip install -r requirements-dev.txt
fi

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Creado .env desde .env.example. Cambia SECRET_KEY y ADMIN_PASSWORD."
fi

exec "$VENV_DIR/bin/uvicorn" app.main:app --reload --host 0.0.0.0 --port 8010
