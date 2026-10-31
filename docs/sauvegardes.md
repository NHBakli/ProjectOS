# Sauvegardes

Plane et n8n sont sauvegardés **sur ton poste**, chiffrés.

## Ce qui est sauvegardé

| Application | Contenu | Interruption |
|---|---|---|
| Plane | Base PostgreSQL (`pg_dump`) + fichiers MinIO | Aucune |
| n8n | Volume complet (base SQLite, réglages) | n8n arrêté ~30 s, puis relancé automatiquement |

Chaque sauvegarde contient un **manifeste** : ce qu'elle contient (nombre de tickets, de workflows…). Le test de restauration s'en sert pour comparer.

Les fichiers sont chiffrés sur le VPS (gpg, AES-256) **avant** d'en sortir.
Destination : `~/projectos-backups/plane-DATE/` et `~/projectos-backups/n8n-DATE/`.

## 1. Créer la phrase de passe (une seule fois)

```bash
./scripts/generate-secrets.sh backup
```

Utilise **le même mot de passe Vault** que pour Plane et n8n.

> ⚠️ Sans `backup.vault.yml` et son mot de passe, les sauvegardes sont illisibles. Garde une copie hors du poste.

## 2. Sauvegarder

Au moins une fois par semaine, et **avant chaque mise à jour**.

```bash
ansible-playbook -i ~/.config/projectos/hosts.yml --ask-vault-pass \
  -e @$HOME/.config/projectos/backup.vault.yml \
  infrastructure/ansible/playbooks/backup.yml
```

**Attendu :** deux dossiers créés, `failed=0`.

## 3. Tester la restauration

Chaque test remonte la **dernière** sauvegarde dans un namespace jetable, compare avec le manifeste, puis supprime tout. **La production n'est pas touchée.**

Plane :

```bash
ansible-playbook -i ~/.config/projectos/hosts.yml --ask-vault-pass \
  -e restore_test_approved=true \
  -e backup_dir=$(ls -d $HOME/projectos-backups/plane-* | tail -1) \
  -e @$HOME/.config/projectos/backup.vault.yml \
  -e @$HOME/.config/projectos/plane-secrets.vault.yml \
  infrastructure/ansible/playbooks/restore-test-plane.yml
```

n8n (vérifie aussi que la clé n8n déchiffre bien les identifiants) :

```bash
ansible-playbook -i ~/.config/projectos/hosts.yml --ask-vault-pass \
  -e restore_test_approved=true \
  -e backup_dir=$(ls -d $HOME/projectos-backups/n8n-* | tail -1) \
  -e @$HOME/.config/projectos/backup.vault.yml \
  -e @$HOME/.config/projectos/n8n-secrets.vault.yml \
  infrastructure/ansible/playbooks/restore-test-n8n.yml
```

**Attendu :** `Restauration identique au manifeste`.

Teste après la première sauvegarde, puis une fois par mois.

## Restaurer pour de vrai

> ⏳ Procédure pas encore automatisée. Fais-toi accompagner.

| Application | Principe |
|---|---|
| Plane | Arrêter Plane, réimporter la base (`pg_restore --clean`), remettre les fichiers MinIO, relancer avec les **mêmes** secrets |
| n8n | Arrêter n8n, remplacer le contenu du volume par l'archive, relancer avec la **même** clé |

## Pas encore couvert

| Point | Pourquoi c'est important |
|---|---|
| Copie hors du poste | Si ton poste disparaît, les sauvegardes aussi. Copie `~/projectos-backups/` sur un disque externe ou dans un cloud. |
| Sauvegarde automatique | Pour l'instant, il faut lancer la commande soi-même. |
| K3s (`/var/lib/rancher/k3s/server/`) | Sans lui, on réinstalle le cluster puis on restaure les applications : faisable, juste plus long. |

Les certificats HTTPS n'ont pas besoin de sauvegarde : ils sont réémis automatiquement.
