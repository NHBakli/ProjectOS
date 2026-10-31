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
| Clé n8n (à venir) | Fichier Vault | Identifiants n8n illisibles |

## Secrets Plane

Générés par `scripts/generate-plane-secrets.sh`, créés par `deploy-plane.yml` dans le namespace `plane` :

| Secret Kubernetes | Contenu |
|---|---|
| `plane-app-keys` | Clés de l'application. **Ne jamais les changer** après l'installation. |
| `plane-app-env` | Adresses de connexion à PostgreSQL, Redis, RabbitMQ |
| `plane-live-env` | Adresse de Redis |
| `plane-postgres` | Compte PostgreSQL |
| `plane-rabbitmq` | Compte RabbitMQ |
| `plane-doc-store` | Compte MinIO (stockage des fichiers) |

## Lire un fichier Vault

```bash
ansible-vault view ~/.config/projectos/plane-secrets.vault.yml
```

À faire seulement si nécessaire : la commande affiche les secrets à l'écran.
