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
dir="$(dirname "$out")"
mkdir -p "$dir"

# Un seul mot de passe Vault pour tous les fichiers : sinon un playbook qui en
# charge plusieurs échoue au déchiffrement.
unset ANSIBLE_VAULT_PASSWORD_FILE
read -rsp "Mot de passe Vault (le même pour tous les fichiers) : " vault_pw; echo >&2
read -rsp "Confirmer : " vault_pw_confirm; echo >&2
if [[ -z "$vault_pw" || "$vault_pw" != "$vault_pw_confirm" ]]; then
  echo "Refus : mots de passe vides ou différents." >&2
  exit 1
fi
pw_file="$(mktemp -p /dev/shm 2>/dev/null || mktemp)"
trap 'rm -f "$pw_file"' EXIT
printf '%s' "$vault_pw" > "$pw_file"

for existing in "$dir"/*.vault.yml; do
  [[ -e "$existing" ]] || continue
  if ! ansible-vault view --vault-password-file "$pw_file" "$existing" >/dev/null 2>&1; then
    echo "Refus : ce mot de passe n'ouvre pas $existing. Utilise le mot de passe Vault commun." >&2
    exit 1
  fi
done

# Lettres et chiffres uniquement : certains mots de passe sont insérés dans des URL.
python3 -I - "$kind" <<'PY' | ansible-vault encrypt --vault-password-file "$pw_file" --output "$out" -
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
