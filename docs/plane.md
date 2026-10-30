# Plane Community Edition — déploiement V1

Chart `plane-ce` 1.8.5 (Plane v1.4.2), déployé par le contrôleur Helm intégré
à K3s (`HelmChart` `plane-app` dans `kube-system`, cible le namespace `plane`).
Valeurs versionnées : `helm/plane-ce-values.yaml` ; le nom d'hôte est injecté
depuis le fichier privé `platform.yml` (`plane.<base>`).

## Composants

| Type | Composants |
|---|---|
| Deployments | web, space, admin, live, api, worker, beat-worker |
| StatefulSets (PVC `local-path`) | PostgreSQL 15 (10 Gi), Valkey/Redis (1 Gi), RabbitMQ (1 Gi), MinIO (10 Gi) |
| Jobs | migrations de la base, création du bucket `uploads` |
| Entrée | `IngressRoute` Traefik sur `websecure` + redirection HTTP→HTTPS |
| TLS | `Certificate` `plane-tls` émis par `letsencrypt-prod` |

Les bases et services internes ne sont pas exposés : seule l'interface passe
par Traefik. Le chart ne crée aucun Secret ; les six Secrets sont créés par le
playbook à partir du fichier Vault (voir [secrets.md](secrets.md)).

## 1. Générer les secrets (une seule fois)

```bash
./scripts/generate-plane-secrets.sh
```

Le script demande un **mot de passe Vault** et écrit
`~/.config/projectos/plane-secrets.vault.yml`, chiffré. Les valeurs ne sont ni
affichées ni écrites en clair. Il refuse d'écraser un fichier existant :
régénérer `plane_secret_key` ou les mots de passe rendrait les données
illisibles ou désynchronisées.

**Conserver le mot de passe Vault et une copie du fichier hors du VPS** : ils
sont indispensables à une restauration.

## 2. Déployer

```bash
export ANSIBLE_CONFIG=infrastructure/ansible.cfg
ansible-playbook -i ~/.config/projectos/hosts.yml --ask-vault-pass \
  -e plane_deploy_approved=true \
  -e @$HOME/.config/projectos/platform.yml \
  -e @$HOME/.config/projectos/plane-secrets.vault.yml \
  infrastructure/ansible/playbooks/deploy-plane.yml
```

Durée : 5 à 15 minutes au premier passage (téléchargement des images). Le
playbook attend le certificat, l'installation Helm, les StatefulSets, les
Jobs et les Deployments, puis vérifie `/` et `/api/instances/` en HTTPS avec
validation du certificat. Une seconde exécution doit finir avec `changed=0`.

## 3. Créer l'administrateur immédiatement

Ouvrir `https://plane.<base>/god-mode/` et créer le compte administrateur de
l'instance **dès la fin du déploiement** : tant qu'il n'existe pas, la première
personne qui accède à cette page en prend le contrôle.

## Mise à jour et retour arrière

Changer `planeVersion` / la version du chart dans un commit, puis relancer le
playbook ; sauvegarder PostgreSQL et MinIO **avant** (voir
[recovery.md](recovery.md)). Les Jobs de migration sont recréés à chaque
révision Helm.

Supprimer le `HelmChart` désinstalle les workloads mais ne supprime pas
forcément les PVC : ne jamais supprimer les PVC ou le namespace `plane` sans
sauvegarde restaurée et vérifiée.
