# Secrets

## Règles

- **Jamais dans Git**, jamais affichés dans le terminal.
- Stockés dans des fichiers **Ansible Vault** chiffrés, dans `~/.config/projectos/`.
- Créés dans le cluster par les playbooks, avec les logs masqués (`no_log`).
- Ne pas les passer en ligne de commande (`-e mot_de_passe=...`) : ils resteraient dans l'historique du shell.

## Où sont-ils ?

| Secret | Emplacement | Si perdu |
|---|---|---|
| Mot de passe Vault | Ta tête / ton gestionnaire de mots de passe | Fichiers Vault illisibles |
| Secrets Plane | `~/.config/projectos/plane-secrets.vault.yml` | Plane non restaurable |
| Phrase de passe des sauvegardes | `~/.config/projectos/backup.vault.yml` | Sauvegardes illisibles |
| Token et datastore K3s | `/var/lib/rancher/k3s/server/` sur le VPS | Cluster non restaurable |
| kubeconfig admin | `~/.kube/projectos.yaml` | Se récupère sur le VPS |
| Clé n8n | `~/.config/projectos/n8n-secrets.vault.yml` | Identifiants n8n illisibles |

## Secrets Plane

Générés par `scripts/generate-secrets.sh plane`, créés par `deploy-plane.yml` dans le namespace `plane` :

| Secret Kubernetes | Contenu |
|---|---|
| `plane-app-keys` | Clés de l'application. **Ne jamais les changer** après l'installation. |
| `plane-app-env` | Adresses de connexion à PostgreSQL, Redis, RabbitMQ |
| `plane-live-env` | Adresse de Redis |
| `plane-postgres` | Compte PostgreSQL |
| `plane-rabbitmq` | Compte RabbitMQ |
| `plane-doc-store` | Compte MinIO (stockage des fichiers) |

## Générer des secrets

```bash
./scripts/generate-secrets.sh plane    # ou backup, ou n8n
```

Le script refuse d'écraser un fichier existant. Il refuse aussi un mot de passe Vault qui n'ouvre pas les fichiers déjà présents : **un seul mot de passe pour tout**.

## Erreur « Decryption failed »

Un fichier a été chiffré avec un autre mot de passe. Remets le mot de passe commun (les secrets ne changent pas) :

```bash
ansible-vault rekey ~/.config/projectos/NOM-DU-FICHIER.vault.yml
```

Saisis d'abord l'ancien mot de passe, puis le mot de passe commun.

Ancien mot de passe oublié ? Tant que l'application tourne, ses secrets sont encore dans le cluster. Exemple pour n8n : on recrée le fichier depuis le Secret, sans afficher la clé.

```bash
mv ~/.config/projectos/n8n-secrets.vault.yml ~/.config/projectos/n8n-secrets.vault.yml.ancien
( umask 077
  ssh $VPS_USER@$VPS_IP \
    "sudo k3s kubectl -n n8n get secret n8n-secrets -o jsonpath='{.data.N8N_ENCRYPTION_KEY}'" \
  | base64 -d \
  | python3 -c "import sys; print('---'); print(\"n8n_encryption_key: '\" + sys.stdin.read().strip() + \"'\")" \
  | ansible-vault encrypt --output ~/.config/projectos/n8n-secrets.vault.yml - )
```

Contrôle : relancer `deploy-n8n.yml`. La mise à jour du Secret doit être **skipped** (clé identique).

## Lire un fichier Vault

```bash
ansible-vault view ~/.config/projectos/plane-secrets.vault.yml
```

À faire seulement si nécessaire : la commande affiche les secrets à l'écran.
