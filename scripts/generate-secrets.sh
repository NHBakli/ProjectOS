#!/usr/bin/env bash
# Génère des secrets aléatoires et les écrit directement chiffrés par Ansible
# Vault. Les valeurs ne sont jamais affichées ni écrites en clair.
#   plane  : clés et mots de passe de Plane
#   backup : phrase de passe des sauvegardes
#   n8n    : clé de chiffrement de n8n
set -euo pipefail

kind="${1:-}"
case "$kind" in
  plane)  default_out=plane-secrets.vault.yml ;;
  backup) default_out=backup.vault.yml ;;
  n8n)    default_out=n8n-secrets.vault.yml ;;
  *) echo "Usage : $0 plane|backup|n8n [fichier]" >&2; exit 2 ;;
esac
out="${2:-$HOME/.config/projectos/$default_out}"

if [[ -e "$out" ]]; then
  echo "Refus : $out existe déjà. Le remplacer rendrait les données ou sauvegardes illisibles." >&2
  exit 1
fi

umask 077
mkdir -p "$(dirname "$out")"

# Lettres et chiffres uniquement : certains mots de passe sont insérés dans des URL.
python3 -I - "$kind" <<'PY' | ansible-vault encrypt --output "$out" -
import secrets
import string
import sys

alphabet = string.ascii_letters + string.digits
fields = {
    'plane': {
        'plane_secret_key': 50,
        'plane_live_server_secret_key': 40,
        'plane_postgres_password': 32,
        'plane_rabbitmq_password': 32,
        'plane_minio_password': 32,
    },
    'backup': {'projectos_backup_passphrase': 48},
    'n8n': {'n8n_encryption_key': 64},
}[sys.argv[1]]

print('---')
for name, length in fields.items():
    print(f"{name}: '{''.join(secrets.choice(alphabet) for _ in range(length))}'")
PY

echo "Secrets « $kind » chiffrés dans $out"
