# Sauvegardes

Les sauvegardes de Plane sont rapatriées **sur ton poste**, chiffrées.

## Ce qui est sauvegardé

| Donnée | Comment |
|---|---|
| Base Plane (projets, tickets, comptes…) | Export PostgreSQL (`pg_dump`) |
| Fichiers joints | Archive du volume MinIO |
| Manifeste | Nombre d'utilisateurs, projets, tickets et fichiers au moment de la sauvegarde |

Les fichiers sont chiffrés sur le VPS (gpg, AES-256) **avant** d'en sortir.
Destination : `~/projectos-backups/plane-<date>/`.

## 1. Créer la phrase de passe (une seule fois)

```bash
./scripts/generate-backup-secret.sh
```

Utilise **le même mot de passe Vault** que pour Plane. Le script crée `~/.config/projectos/backup.vault.yml`.

> ⚠️ Sans ce fichier et son mot de passe, les sauvegardes sont illisibles. Garde une copie hors du poste.

## 2. Sauvegarder

À faire au moins une fois par semaine, et **avant chaque mise à jour**.

```bash
ansible-playbook -i ~/.config/projectos/hosts.yml --ask-vault-pass \
  -e @$HOME/.config/projectos/backup.vault.yml \
  infrastructure/ansible/playbooks/backup-plane.yml
```

**Attendu :** le dossier créé et le contenu sauvegardé (`users`, `projects`, `issues`…).

## 3. Tester la restauration

Remonte la sauvegarde dans un namespace jetable, compare les chiffres avec le manifeste, puis supprime tout. **La production n'est pas touchée.**

```bash
ansible-playbook -i ~/.config/projectos/hosts.yml --ask-vault-pass \
  -e restore_test_approved=true \
  -e backup_dir=$HOME/projectos-backups/plane-<date> \
  -e @$HOME/.config/projectos/backup.vault.yml \
  -e @$HOME/.config/projectos/plane-secrets.vault.yml \
  infrastructure/ansible/playbooks/restore-test-plane.yml
```

**Attendu :** `Restauration identique au manifeste`.

Fais ce test après la première sauvegarde, puis une fois par mois.

## Restaurer pour de vrai

> ⏳ Procédure pas encore automatisée. Fais-toi accompagner.

Principe : arrêter Plane, réimporter la base (`pg_restore --clean`), remettre les fichiers MinIO, relancer Plane avec **les mêmes secrets** (`plane-secrets.vault.yml`).

## Pas encore couvert

| Donnée | Pourquoi c'est important |
|---|---|
| Copie hors du poste | Si ton poste disparaît, les sauvegardes aussi. Copie le dossier sur un disque externe ou dans un cloud. |
| Sauvegarde automatique | Pour l'instant, il faut lancer la commande soi-même. |
| K3s (`/var/lib/rancher/k3s/server/`) | Sans lui, on réinstalle le cluster puis on restaure Plane : c'est faisable, juste plus long. |
| n8n | À ajouter quand n8n sera déployé. |

Les certificats HTTPS n'ont pas besoin de sauvegarde : ils sont réémis automatiquement.
