#!/usr/bin/env bash
# Génère la phrase de passe qui chiffre les sauvegardes, directement dans un
# fichier Ansible Vault. Elle n'est jamais affichée ni écrite en clair.
set -euo pipefail

out="${1:-$HOME/.config/projectos/backup.vault.yml}"

if [[ -e "$out" ]]; then
  echo "Refus : $out existe déjà. La remplacer rendrait les anciennes sauvegardes illisibles." >&2
  exit 1
fi

umask 077
mkdir -p "$(dirname "$out")"

python3 -I - <<'PY' | ansible-vault encrypt --output "$out" -
import secrets
import string

alphabet = string.ascii_letters + string.digits
print('---')
print(f"projectos_backup_passphrase: '{''.join(secrets.choice(alphabet) for _ in range(48))}'")
PY

echo "Phrase de passe des sauvegardes chiffrée dans $out"
