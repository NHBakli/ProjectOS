# 4. Déployer Plane

Plane Community Edition, chart `plane-ce` 1.8.5 (Plane v1.4.2).
Adresse : `https://plane.<ton-domaine>`.

## Ce qui est installé

| Élément | Détail |
|---|---|
| Application | Interface web, API, workers, espace public, administration |
| Données | PostgreSQL (10 Gio), MinIO pour les fichiers (10 Gio), Redis, RabbitMQ |
| Accès | HTTPS uniquement. HTTP redirige vers HTTPS. |

Les bases de données ne sont **pas** accessibles depuis Internet.

## Étapes

**1. Générer les secrets** (une seule fois)

```bash
./scripts/generate-secrets.sh plane
```

- Choisis un **mot de passe Vault** et garde-le précieusement.
- Le script crée `~/.config/projectos/plane-secrets.vault.yml`, chiffré.
- Il refuse d'écraser un fichier existant : c'est voulu.

> ⚠️ Sans ce fichier **et** son mot de passe, les données Plane ne sont pas restaurables. Garde une copie des deux hors du VPS, par exemple dans un gestionnaire de mots de passe.

**2. Déployer** (5 à 15 min la première fois)

```bash
ansible-playbook -i ~/.config/projectos/hosts.yml --ask-vault-pass \
  -e plane_deploy_approved=true \
  -e @$HOME/.config/projectos/platform.yml \
  -e @$HOME/.config/projectos/plane-secrets.vault.yml \
  infrastructure/ansible/playbooks/deploy-plane.yml
```

**Attendu :** `Plane répond en HTTPS`, `failed=0`.

**3. Créer le compte admin, tout de suite**

Ouvre `https://plane.<ton-domaine>/god-mode/` et crée le compte.

> ⚠️ Tant qu'il n'existe pas, la première personne qui ouvre cette page devient admin.

## En cas de problème

| Symptôme | Action |
|---|---|
| Le playbook attend longtemps | Normal au 1er lancement (images à télécharger) |
| Un Pod en erreur | `sudo k3s kubectl -n plane get pods`, puis `sudo k3s kubectl -n plane logs NOM_DU_POD` |
| Erreur Vault | Vérifier le mot de passe Vault |

## Mettre à jour

1. **Sauvegarder** d'abord ([sauvegardes.md](sauvegardes.md)).
2. Changer la version dans `helm/plane-ce-values.yaml` et dans `deploy-plane.yml`.
3. Relancer la commande de l'étape 2.

## Retour arrière

```bash
sudo k3s kubectl -n kube-system delete helmchart plane-app
```

Les volumes de données restent. **Ne jamais** supprimer le namespace `plane` ni ses volumes sans une sauvegarde testée.
