# Sauvegardes

> ⏳ **Pas encore en place.** Ne mets pas de données importantes dans Plane ou n8n avant.

## Quoi sauvegarder

| Donnée | Quoi copier | Test de restauration |
|---|---|---|
| Plane | Export PostgreSQL + fichiers MinIO | Retrouver un projet, un ticket, une pièce jointe |
| n8n | Volume n8n + `N8N_ENCRYPTION_KEY` | Retrouver un workflow, relire un identifiant |
| K3s | `/var/lib/rancher/k3s/server/db/` + `/var/lib/rancher/k3s/server/token` | Remonter le cluster sur une machine de test |
| Secrets | Fichiers Vault + mot de passe Vault | Déchiffrer avec `ansible-vault view` |

Les certificats HTTPS n'ont pas besoin d'être sauvegardés : ils sont réémis automatiquement.

## Principes

- Les sauvegardes vont **hors du VPS**. Si le VPS disparaît, les volumes disparaissent avec lui.
- Elles sont **chiffrées**.
- Une sauvegarde qui n'a jamais été restaurée ne compte pas : **tester la restauration**.
- Toujours sauvegarder avant une mise à jour.

## À décider

- [ ] Destination : stockage objet (S3…), autre serveur, service de sauvegarde
- [ ] Fréquence. Proposition : chaque jour, garder 7 jours + 4 semaines
- [ ] Qui est prévenu si une sauvegarde échoue
