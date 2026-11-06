#!/usr/bin/env bash
# Lance le générateur de PLD dans un environnement Python isolé.
# Dépendances : pld/requirements.txt (versions et empreintes sha256 figées, pip --require-hashes).
# L'environnement est recréé seulement si requirements.txt change.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv="${PROJECTOS_PLD_VENV:-$HOME/.cache/projectos/pld-venv}"
req="$repo_root/pld/requirements.txt"
stamp="$venv/.requirements.sha256"
want="$(sha256sum "$req" | cut -d' ' -f1)"

if [[ ! -x "$venv/bin/python" || "$(cat "$stamp" 2>/dev/null || true)" != "$want" ]]; then
  echo "Préparation de l'environnement Python dans $venv (une seule fois)…" >&2
  if [[ -d "$venv" && ! -f "$venv/pyvenv.cfg" ]]; then
    echo "✗ $venv existe mais n'est pas un environnement Python : je ne le touche pas." >&2
    exit 1
  fi
  python3 -m venv --clear "$venv"
  "$venv/bin/python" -m pip install --quiet --disable-pip-version-check \
    --require-hashes --only-binary :all: -r "$req"
  printf '%s\n' "$want" >"$stamp"
fi

exec "$venv/bin/python" "$repo_root/pld/generer_pld.py" "$@"
