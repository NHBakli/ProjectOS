#!/usr/bin/env bash
# Génère les secrets Plane et les écrit directement chiffrés par Ansible Vault.
# Les valeurs ne sont jamais affichées ni écrites en clair sur le disque.
set -euo pipefail

out="${1:-$HOME/.config/projectos/plane-secrets.vault.yml}"

if [[ -e "$out" ]]; then
  echo "Refus : $out existe déjà. Régénérer ces secrets rendrait les données Plane illisibles." >&2
  exit 1
fi

umask 077
mkdir -p "$(dirname "$out")"

# Lettres et chiffres uniquement : les mots de passe sont insérés dans des URL.
python3 -I - <<'PY' | ansible-vault encrypt --output "$out" -
import secrets
import string

alphabet = string.ascii_letters + string.digits


def token(length):
    return ''.join(secrets.choice(alphabet) for _ in range(length))


print('---')
print(f"plane_secret_key: '{token(50)}'")
print(f"plane_live_server_secret_key: '{token(40)}'")
print(f"plane_postgres_password: '{token(32)}'")
print(f"plane_rabbitmq_password: '{token(32)}'")
print(f"plane_minio_password: '{token(32)}'")
PY

echo "Secrets Plane chiffrés dans $out"
