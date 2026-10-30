# 1. Préparer ton poste

À faire une seule fois. Toutes les commandes se lancent depuis la racine du dépôt.

## Outils

| Outil | Pourquoi |
|---|---|
| `ansible-core` 2.16, `ansible-lint`, `yamllint` | Installer et valider |
| Accès SSH au VPS avec ta clé | Ansible passe par SSH |
| `nc`, `curl` | Tests depuis l'extérieur |

```bash
python3 -m pip install -r requirements-validation.txt
ansible-galaxy collection install -r infrastructure/ansible/requirements.yml \
  -p infrastructure/ansible/collections
```

## Fichiers privés

Ils contiennent l'IP et les secrets. Ils vivent **hors du dépôt**, dans `~/.config/projectos/`.

```bash
mkdir -p ~/.config/projectos && chmod 700 ~/.config/projectos
cd infrastructure/ansible/inventories/production
cp hosts.example.yml        ~/.config/projectos/hosts.yml
cp k3s-approval.example.yml ~/.config/projectos/k3s-approval.yml
cp platform.example.yml     ~/.config/projectos/platform.yml
cd -
```

Remplace ensuite les valeurs d'exemple dans chaque fichier :

| Fichier | À remplir |
|---|---|
| `hosts.yml` | IP du VPS, compte admin, chemin de ta clé SSH (`ansible_ssh_private_key_file`) |
| `k3s-approval.yml` | `k3s_api_bind_address` : l'IP du VPS |
| `platform.yml` | `projectos_base_domain` : l'IP avec des tirets + `.sslip.io` (ex. `1-2-3-4.sslip.io`) |
| `plane-secrets.vault.yml` | Rien à la main : créé par un script ([04-plane.md](04-plane.md)) |

## À chaque session

```bash
export ANSIBLE_CONFIG=infrastructure/ansible.cfg
./scripts/validate.sh
```

**Résultat attendu :** `Passed: 0 failure(s), 0 warning(s)`.
